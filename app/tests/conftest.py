"""Fixtures for the app's tests: a learner of their own, and a clean budget record."""

from __future__ import annotations

import asyncio
import socket
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.rules import Rules, load_rules
from juku_data.engine import Databases, create_learner
from juku_data.engine.models import Learner
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings
from juku_testkit.databases import TestDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

sys.path.insert(0, str(Path(__file__).parent))


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def direct_rules() -> Rules:
    rules = load_rules()
    return rules.model_copy(
        update={"delegation": rules.delegation.model_copy(update={"require_gateway_caller": False})}
    )


@pytest.fixture
def key() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
async def juku_mcp_url(
    app_database: TestDatabase,
    dictionary_database: TestDatabase,
    key: ed25519.Ed25519PrivateKey,
    tmp_path: Path,
    mirrored_dictionary: None,
) -> AsyncIterator[str]:
    """Juku's MCP server over HTTP, reached directly (the gateway's place in production)."""
    assert mirrored_dictionary is None
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    settings = McpSettings(
        app_database_url=app_database.sqlalchemy_url,
        dict_database_url=dictionary_database.sqlalchemy_url,
        delegation_public_key=pem.decode(),
        audit_log=tmp_path / "juku-mcp.jsonl",
    )
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(settings, direct_rules()), port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        await task


@pytest.fixture
async def learner(engine_databases: Databases) -> AsyncIterator[Learner]:
    made = await create_learner(engine_databases, nickname="tester", target_level=5)
    yield made
    async with engine_databases.app.begin() as connection:
        await connection.execute(text("DELETE FROM learning.learners WHERE id = :id"), {"id": made.id})


@pytest.fixture
async def clean_budget(app_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with app_engine.begin() as connection:
        await connection.execute(text("TRUNCATE app.model_calls"))
    yield app_engine
