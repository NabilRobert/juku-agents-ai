"""The HTTP app: Juku's MCP server over Streamable HTTP at /mcp, and /healthz.

It listens only on the gateway's upstream network (ops/compose.yaml): the
gateway is the one client, and it authenticates each agent with its own
key before forwarding a call here with the caller stamped in `_meta`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.audit_chain import JUKU_MCP_GENESIS, AuditLog
from juku_common.delegation import Verifier
from juku_common.rules import Rules, load_rules
from juku_data.engine import Databases
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from juku_mcp.search import DictionarySearch
from juku_mcp.server import ServerDeps, build_server
from juku_mcp.settings import McpSettings
from juku_mcp.telemetry import install_tracing

MCP_PATH = "/mcp"
# A small pool: one process, a handful of agents at once (ADR-016's 128 MB container).
POOL_SIZE = 4


def public_key_from_pem(pem: str) -> ed25519.Ed25519PublicKey:
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise ValueError(
            "JUKU_MCP_DELEGATION_PUBLIC_KEY isn't an Ed25519 public key: make one with ops/make-secrets.sh"
        )
    return key


def create_app(settings: McpSettings, rules: Rules | None = None) -> Starlette:
    rules = rules or load_rules()
    install_tracing()
    db = Databases(
        app=create_async_engine(settings.app_database_url, pool_size=POOL_SIZE),
        dictionary=create_async_engine(settings.dict_database_url, pool_size=POOL_SIZE),
    )
    deps = ServerDeps(
        db=db,
        verifier=Verifier(public_key_from_pem(settings.delegation_public_key), rules),
        audit=AuditLog(settings.audit_log, genesis=JUKU_MCP_GENESIS),
        rules=rules,
        words=DictionarySearch(db.dictionary),
    )
    mcp_app = build_server(deps).streamable_http_app(streamable_http_path=MCP_PATH)

    async def healthz(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    mcp_app.add_route("/healthz", healthz, methods=["GET"])

    serve_sessions = mcp_app.router.lifespan_context  # the MCP SDK's own: runs the session manager

    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncGenerator[None]:
        async with serve_sessions(mcp_app):
            yield
        deps.audit.close()
        await db.app.dispose()
        await db.dictionary.dispose()

    mcp_app.router.lifespan_context = lifespan
    return mcp_app
