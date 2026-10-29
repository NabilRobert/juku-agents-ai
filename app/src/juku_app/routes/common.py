"""What every page area shares: the app's context, the signed-in learner, CSRF checks and rendering.

The routers (one per area in this package) reach the app's databases,
chat services and templates through `request.app.state`, set once by
create_web_app (juku_app.web). Every learner page depends on `page`: a
signed-in learner whose consent is on the current notice version (no
activity without it). Every form carries a CSRF token tied to the
session; the islands send it in a header.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from juku_common.rules import Rules
from juku_data import engine
from juku_data.engine import Databases, LearnerNotFoundError
from juku_data.engine.models import Learner
from sqlalchemy import text

from juku_app import assets, i18n
from juku_app.chat import ChatServices
from juku_app.consent import has_current_consent
from juku_app.ruby import furigana_to_ruby

TEMPLATES = Path(__file__).parent.parent / "templates"
TIMEZONES = ("Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Tokyo")
LEVELS = (5, 4, 3, 2)


@dataclass(frozen=True)
class WebContext:
    """The app's shared services, on app.state.web."""

    db: Databases
    rules: Rules
    chat: ChatServices
    views: Jinja2Templates
    admin_public_ids: frozenset[str]


@dataclass
class Redirect(Exception):
    """Raised by a dependency to send the visitor elsewhere (303)."""

    location: str


@dataclass(frozen=True)
class Page:
    """What every learner page gets: the learner, their nickname, and their local date."""

    learner: Learner
    nickname: str
    today: date = field(default_factory=date.today)


def web(request: Request) -> WebContext:
    return cast(WebContext, request.app.state.web)


def templates() -> Jinja2Templates:
    environment = Jinja2Templates(directory=TEMPLATES)
    environment.env.add_extension("jinja2.ext.i18n")
    environment.env.install_gettext_callables(i18n.gettext, i18n.ngettext, newstyle=True)  # type: ignore[attr-defined]
    helpers = cast(dict[str, Any], environment.env.globals)  # pyright: ignore[reportUnknownMemberType]
    helpers.update(island=assets.island, stylesheet=assets.stylesheet, ruby=furigana_to_ruby)
    return environment


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


def check_csrf(request: Request, sent: str | None) -> None:
    expected = request.session.get("csrf")
    if not isinstance(expected, str) or not sent or not secrets.compare_digest(expected, sent):
        raise Redirect("/csrf")


async def form_csrf(request: Request, csrf: str = Form("")) -> None:
    check_csrf(request, csrf)


async def header_csrf(request: Request) -> None:
    check_csrf(request, request.headers.get("X-CSRF-Token"))


def render(request: Request, name: str, **context: Any) -> HTMLResponse:
    # The page's name, for real-user timings (FE8): "beranda" for /beranda.
    page_name = request.url.path.strip("/").split("/")[0] or "root"
    return web(request).views.TemplateResponse(
        request, name, {"csrf": csrf_token(request), "page_name": page_name, **context}
    )


async def nickname_of(request: Request, learner: Learner) -> str:
    async with web(request).db.app.connect() as connection:
        return str(
            await connection.scalar(text("SELECT nickname FROM learning.learners WHERE id = :id"), {"id": learner.id})
        )


async def signed_in(request: Request) -> Learner:
    public_id = request.session.get("learner")
    if not isinstance(public_id, str):
        raise Redirect("/masuk")
    try:
        return await engine.get_learner(web(request).db, public_id)
    except LearnerNotFoundError:
        request.session.clear()
        raise Redirect("/masuk") from None


async def page(request: Request, learner: Learner = Depends(signed_in)) -> Page:  # noqa: B008 (FastAPI's dependency idiom)
    """A learner page: signed in, and consent on the current version (no activity without it)."""
    if not await has_current_consent(web(request).db.app, learner.id):
        raise Redirect("/persetujuan")
    today = datetime.now(UTC).astimezone(ZoneInfo(learner.timezone)).date()
    return Page(learner=learner, nickname=await nickname_of(request, learner), today=today)


async def admin(request: Request, learner: Learner = Depends(signed_in)) -> Learner:  # noqa: B008
    """Arthur only: anyone else gets the same 404 as a page that doesn't exist."""
    if learner.public_id not in web(request).admin_public_ids:
        raise HTTPException(status_code=404)
    return learner
