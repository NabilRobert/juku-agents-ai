"""SM4: request_replan, the one action tool, only queues a Keiko run, at most once a learner's day."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import Databases
from juku_mcp.server import build_server
from mcp import Client
from mcp_helpers import Learners, call, make_deps, token_for
from sqlalchemy import text

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the server lands in the next commit")


async def queued(db: Databases, learner_id: int) -> int:
    async with db.app.connect() as connection:
        count = await connection.scalar(
            text("SELECT count(*) FROM learning.replan_requests WHERE learner_id = :id"), {"id": learner_id}
        )
    return int(count or 0)


@pytest.mark.guardrail("replan.max_requests_per_day")
async def test_a_second_request_on_the_same_day_is_not_queued(
    client: Client, signer: Signer, learners: Learners, engine_databases: Databases
) -> None:
    first = await call(client, "request_replan", token_for(signer, learners.a))
    second = await call(client, "request_replan", token_for(signer, learners.a))
    assert (first.is_error, first.body["queued"]) == (False, True)
    assert (second.is_error, second.body["queued"]) == (False, False)
    assert "besok" in second.body["message"]
    assert await queued(engine_databases, learners.a.id) == 1


@pytest.mark.guardrail("replan.max_requests_per_day")
async def test_the_daily_cap_comes_from_the_rule_file(
    engine_databases: Databases, key: ed25519.Ed25519PrivateKey, signer: Signer, learners: Learners, audit_path: Path
) -> None:
    rules = load_rules()
    rules = rules.model_copy(
        update={
            "replan": rules.replan.model_copy(update={"max_requests_per_day": 2}),
            "delegation": rules.delegation.model_copy(update={"require_gateway_caller": False}),
        }
    )
    async with Client(build_server(make_deps(engine_databases, key, audit_path, rules=rules))) as client:
        answers = [await call(client, "request_replan", token_for(signer, learners.b)) for _ in range(3)]
    assert [answer.body["queued"] for answer in answers] == [True, True, False]


async def test_the_request_records_who_asked(
    client: Client, signer: Signer, learners: Learners, engine_databases: Databases
) -> None:
    await call(client, "request_replan", token_for(signer, learners.a))
    async with engine_databases.app.connect() as connection:
        chain = await connection.scalar(
            text("SELECT actor_chain FROM learning.replan_requests WHERE learner_id = :id"), {"id": learners.a.id}
        )
    assert chain == ["shiori"]


async def test_keiko_cannot_request_a_replan(client: Client, signer: Signer, learners: Learners) -> None:
    keiko = signer.delegate(token_for(signer, learners.a), to_agent="keiko", tools=["get_progress"])
    assert (await call(client, "request_replan", keiko)).body["refused"] == "out_of_scope"


def test_today_is_the_learners_own_day() -> None:
    from juku_mcp.server import local_day

    late_evening_utc = datetime(2026, 11, 2, 20, 0, tzinfo=UTC)
    assert local_day(late_evening_utc, "Asia/Tokyo").isoformat() == "2026-11-03"
    assert local_day(late_evening_utc, "Asia/Jakarta").isoformat() == "2026-11-03"
    assert local_day(late_evening_utc, "Europe/London").isoformat() == "2026-11-02"
