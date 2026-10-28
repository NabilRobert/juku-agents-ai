"""Fixtures for Juku's MCP server: keys, a signer, two learners, and a client on the server in memory."""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import Databases, create_learner, mark_known
from juku_mcp.server import build_server
from mcp import Client
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent))

from mcp_helpers import Learners, connected, make_deps


@pytest.fixture
def key() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
def signer(key: ed25519.Ed25519PrivateKey) -> Signer:
    return Signer(key, load_rules())


@pytest.fixture
def audit_path(tmp_path: Path) -> Path:
    return tmp_path / "juku-mcp-audit.jsonl"


async def some_words(db: Databases, count: int, offset: int) -> list[str]:
    async with db.app.connect() as connection:
        found = await connection.scalars(
            text("SELECT word_id FROM learning.dictionary_words WHERE level = 5 ORDER BY word_id OFFSET :o LIMIT :n"),
            {"o": offset, "n": count},
        )
        return [str(word_id) for word_id in found]


@pytest.fixture
async def learners(engine_databases: Databases) -> Learners:
    """Two learners with different known words, so any leak between them shows."""
    a = await create_learner(engine_databases, nickname="A", target_level=5)
    b = await create_learner(engine_databases, nickname="B", target_level=4, timezone="Asia/Tokyo")
    at = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    for word in await some_words(engine_databases, 30, 0):
        await mark_known(engine_databases, a.id, word, at)
    for word in await some_words(engine_databases, 80, 200):
        await mark_known(engine_databases, b.id, word, at)
    return Learners(a=a, b=b)


@pytest.fixture
async def client(
    engine_databases: Databases, key: ed25519.Ed25519PrivateKey, audit_path: Path
) -> AsyncIterator[Client]:
    async with connected(build_server(make_deps(engine_databases, key, audit_path))) as client:
        yield client
