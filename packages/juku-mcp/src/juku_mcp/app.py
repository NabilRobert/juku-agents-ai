"""The HTTP app: Juku's MCP server over Streamable HTTP at /mcp, and /healthz.

It listens only on the gateway's upstream network (ops/compose.yaml): the
gateway is the one client, and it authenticates each agent with its own
key before forwarding a call here with the caller stamped in `_meta`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from juku_common.audit_chain import JUKU_MCP_GENESIS, AuditLog
from juku_common.delegation import Verifier, public_key_from_pem
from juku_common.rules import Rules, load_rules
from juku_data.engine import Databases
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse

from juku_mcp.search import DictionarySearch
from juku_mcp.server import ServerDeps, build_server
from juku_mcp.settings import McpSettings
from juku_mcp.telemetry import install_tracing

MCP_PATH = "/mcp"


def databases(settings: McpSettings, rules: Rules) -> Databases:
    """Fixed pools from the rule file, no overflow, so juku_mcp stays within its share of the provider's limit."""
    budget = rules.database
    return Databases(
        app=create_async_engine(settings.app_database_url, pool_size=budget.mcp_pool, max_overflow=0),
        dictionary=create_async_engine(settings.dict_database_url, pool_size=budget.mcp_dict_pool, max_overflow=0),
    )


def create_app(settings: McpSettings, rules: Rules | None = None) -> Starlette:
    rules = rules or load_rules()
    install_tracing()
    db = databases(settings, rules)
    deps = ServerDeps(
        db=db,
        verifier=Verifier(public_key_from_pem(settings.delegation_public_key, "JUKU_MCP_DELEGATION_PUBLIC_KEY"), rules),
        audit=AuditLog(settings.audit_log, genesis=JUKU_MCP_GENESIS),
        rules=rules,
        words=DictionarySearch(db.dictionary),
    )
    # Explicit, because the SDK's default only serves localhost Host headers: the gateway's calls
    # to juku-mcp:8000 would all be refused with 421. No allowed origins: no browser calls this.
    security = TransportSecuritySettings(allowed_hosts=settings.allowed_hosts)
    mcp_app = build_server(deps).streamable_http_app(streamable_http_path=MCP_PATH, transport_security=security)

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
