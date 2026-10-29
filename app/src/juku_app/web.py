"""The web app (Phase 2 UI1-UI3, FE1): server-rendered pages in Indonesian, with Vue islands where interactive.

This module only assembles the app: its services, the session cookie, the
request log, the static files, and one router per page area
(juku_app.routes). A learner's first visit: an invite code (/masuk), the
consent notice (/persetujuan), then their details (/mulai); after that,
every page needs a signed-in learner whose consent is on the current
version (routes/common.py: page).

The $0 pages call the learning engine directly; only chat calls a model,
through Shiori and the budget guard. The browser holds no model or MCP
key (UI2): it talks only to this app.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from pydantic_ai.models import Model
from starlette.middleware.sessions import SessionMiddleware

from juku_app import assets
from juku_app.budget import BudgetGuard
from juku_app.chat import ChatServices
from juku_app.moderation import Moderator
from juku_app.routes import account, admin, chat, learning, memory, reports, settings, site
from juku_app.routes.common import Redirect, WebContext, templates
from juku_app.shiori import build_shiori, juku_toolset

SESSION_DAYS = 30
ROUTERS = (account, settings, learning, chat, memory, reports, admin, site)


@dataclass(frozen=True)
class WebDeps:
    db: Databases
    rules: Rules
    signer: Signer
    session_secret: str
    model: Model
    juku_mcp_url: str
    shiori_gateway_key: str | None
    moderator: Moderator
    crisis_line: str
    secure_cookies: bool = True
    # Who may open the Run Inspector (AG3): Arthur's own public ID, from the settings.
    admin_public_ids: frozenset[str] = frozenset()


def _context(deps: WebDeps, guard: BudgetGuard) -> WebContext:
    chat_services = ChatServices(
        agent=build_shiori(deps.model, juku_toolset(deps.juku_mcp_url, deps.shiori_gateway_key)),
        guard=guard,
        moderator=deps.moderator,
        signer=deps.signer,
        app=deps.db.app,
        crisis_line=deps.crisis_line,
    )
    return WebContext(
        db=deps.db, rules=deps.rules, chat=chat_services, views=templates(), admin_public_ids=deps.admin_public_ids
    )


async def redirect(_: Request, exception: Exception) -> Response:
    """A dependency's Redirect: a 303, or a plain 403 for a form whose CSRF token didn't match."""
    location = exception.location if isinstance(exception, Redirect) else "/masuk"
    if location == "/csrf":
        return HTMLResponse("Formulir kedaluwarsa. Muat ulang halaman, lalu coba lagi.", status_code=403)
    return RedirectResponse(location, status_code=303)


def create_web_app(deps: WebDeps) -> FastAPI:
    guard = BudgetGuard(deps.db.app, deps.rules)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        await guard.sync_pool_sizes()
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.web = _context(deps, guard)
    app.add_middleware(
        SessionMiddleware,
        secret_key=deps.session_secret,
        session_cookie="juku_session",
        max_age=SESSION_DAYS * 24 * 3600,
        same_site="lax",
        https_only=deps.secure_cookies,
    )
    app.mount("/static", StaticFiles(directory=assets.STATIC, check_dir=False), name="static")
    log = structlog.get_logger("juku_app")

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """One line per request: method, route, status and time. Never a body, a query or a form."""
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        log.info(
            "request",
            method=request.method,
            route=getattr(route, "path", "unmatched"),
            status=response.status_code,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response

    app.add_exception_handler(Redirect, redirect)
    for area in ROUTERS:
        app.include_router(area.router)
    return app
