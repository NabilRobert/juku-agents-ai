"""SAF1, direct: the attack suite against Juku's server alone, compared with the committed prediction.

The injections are planted in a fixture copy of the dictionary, never in
the one other tests use (SAF-R1). The gateway run, which needs the
gateway's own environment, is attacks/run_through_gateway.sh.
"""

import asyncio
import socket
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import uvicorn
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.dictionary.load import load_dictionary
from juku_data.engine import Databases, create_learner, mark_known
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings
from juku_testkit.databases import TestDatabase, create_database, drop_database, require_openjlpt
from mcp_helpers import direct_rules
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ATTACKS = Path(__file__).resolve().parents[1] / "attacks"
sys.path.insert(0, str(ATTACKS))

from suite import Target, World, planted_instruction, run_suite  # noqa: E402

pytestmark = [pytest.mark.fitness("FF8"), pytest.mark.timeout(300)]


def prediction() -> dict[str, dict[str, str]]:
    document = cast(dict[str, Any], yaml.safe_load((ATTACKS / "prediction.yaml").read_text(encoding="utf-8")))
    return {attack["id"]: attack for attack in document["attacks"]}


@pytest.fixture(scope="module")
def planted_dictionary() -> Iterator[TestDatabase]:
    """A fixture copy of the dictionary whose example sentences carry the planted instructions."""
    from juku_data.dictionary.source import verify_source

    folder = require_openjlpt()
    database = create_database("juku_test_planted")

    async def load_and_plant() -> None:
        engine = create_async_engine(database.sqlalchemy_url)
        try:
            await load_dictionary(engine, verify_source(folder))
            instructions = " ".join(planted_instruction("PLACEHOLDER").values())
            async with engine.begin() as connection:
                await connection.execute(
                    text("UPDATE ojlpt.sentence SET en = coalesce(en, '') || ' ' || :planted"),
                    {"planted": instructions},
                )
        finally:
            await engine.dispose()

    try:
        asyncio.run(load_and_plant())
        yield database
    finally:
        drop_database(database)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
async def world_and_target(
    app_database: TestDatabase, planted_dictionary: TestDatabase, mirrored_dictionary: None, tmp_path: Path
) -> AsyncIterator[tuple[World, Target]]:
    assert mirrored_dictionary is None
    key = ed25519.Ed25519PrivateKey.generate()
    db = Databases(
        app=create_async_engine(app_database.sqlalchemy_url),
        dictionary=create_async_engine(planted_dictionary.sqlalchemy_url),
    )
    a = await create_learner(db, nickname="A", target_level=5)
    b = await create_learner(db, nickname="B", target_level=5)
    async with db.app.connect() as connection:
        words = list(
            await connection.scalars(text("SELECT word_id FROM learning.dictionary_words ORDER BY word_id LIMIT 40"))
        )
    from datetime import UTC, datetime

    for word in words:
        await mark_known(db, a.id, str(word), datetime(2026, 11, 2, tzinfo=UTC))
    async with db.dictionary.begin() as connection:
        await connection.execute(
            text("UPDATE ojlpt.sentence SET en = replace(en, 'PLACEHOLDER', :b)"), {"b": b.public_id}
        )
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    settings = McpSettings(
        app_database_url=app_database.sqlalchemy_url,
        dict_database_url=planted_dictionary.sqlalchemy_url,
        delegation_public_key=pem.decode(),
        audit_log=tmp_path / "audit.jsonl",
    )
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(settings, direct_rules()), port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    try:
        world = World(signer=Signer(key, load_rules()), learner_a=a.public_id, learner_b=b.public_id)
        yield world, Target(mode="direct", url=f"http://127.0.0.1:{port}/mcp")
    finally:
        server.should_exit = True
        await task
        await db.app.dispose()
        await db.dictionary.dispose()


async def test_every_attack_ends_as_predicted_directly(world_and_target: tuple[World, Target]) -> None:
    world, target = world_and_target
    results = await run_suite(target, world)
    expected = {attack_id: attack["direct"] for attack_id, attack in prediction().items()}
    actual = {attack_id: result for attack_id, result in results.items() if not attack_id.startswith("_")}
    assert actual == expected
