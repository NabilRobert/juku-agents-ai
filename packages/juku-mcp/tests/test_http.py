"""The server over Streamable HTTP, as the gateway reaches it: /healthz, and a tool call with its token."""

import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings
from juku_testkit.databases import TestDatabase
from mcp import Client
from mcp_helpers import Learners, call, direct_rules, token_for

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@pytest.fixture
async def base_url(
    app_database: TestDatabase,
    dictionary_database: TestDatabase,
    key: ed25519.Ed25519PrivateKey,
    tmp_path: Path,
    learners: Learners,  # created first, so the server sees them
) -> AsyncIterator[str]:
    assert learners
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    settings = McpSettings(
        app_database_url=app_database.sqlalchemy_url,
        dict_database_url=dictionary_database.sqlalchemy_url,
        delegation_public_key=pem.decode(),
        audit_log=tmp_path / "audit.jsonl",
    )
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(settings, direct_rules()), port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task


async def test_the_health_check_answers(base_url: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/healthz")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


async def test_a_tool_call_over_http_carries_its_token_in_meta(
    base_url: str, signer: Signer, learners: Learners
) -> None:
    async with Client(f"{base_url}/mcp") as client:
        answer = await call(client, "get_progress", token_for(signer, learners.a))
        refused = await call(client, "get_progress", token_for(signer, learners.a), caller="keiko")
    assert not answer.is_error, answer.text
    assert answer.body["target_level"] == 5
    assert refused.body["refused"] == "actor_mismatch"


async def test_a_call_addressed_to_the_service_name_is_served(base_url: str) -> None:
    # The gateway reaches the server as http://juku-mcp:8000/mcp (ops/gateway/juku-routes.example.yaml),
    # so its Host header is the service name, not localhost.
    async with httpx.AsyncClient(headers={"Host": "juku-mcp:8000"}) as client:
        response = await client.post(f"{base_url}/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert response.status_code == 200, response.text


async def test_a_call_addressed_to_an_unknown_host_is_refused(base_url: str) -> None:
    # DNS-rebinding protection stays on: only the listed hosts are served.
    async with httpx.AsyncClient(headers={"Host": "attacker.example:8000"}) as client:
        response = await client.post(f"{base_url}/mcp", json=INITIALIZE, headers=MCP_HEADERS)
    assert response.status_code == 421
