"""The pages anyone may open, and the app's own signals: the health check, the data notice, the language
switch, real-user timings."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from juku_app import i18n
from juku_app.routes.common import form_csrf, render, web

# Where the language switch returns to when the page it came from can't be trusted.
HOME = "/beranda"

router = APIRouter()


class WebVital(BaseModel):
    page: str = Field(max_length=40, pattern=r"^[a-z-]+$")
    metric: Literal["LCP", "INP", "CLS"]
    value: float = Field(ge=0, le=600_000)


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/tentang-data")
async def about_the_data(request: Request) -> HTMLResponse:
    return render(request, "tentang_data.html")


def same_site_path(back: str) -> str:
    """The path to return to, only if it's on this site: `//other.example` or a full URL would leave Juku."""
    is_path = back.startswith("/") and not back.startswith("//")
    is_plain = "\\" not in back and all(character.isprintable() for character in back)
    return back if is_path and is_plain else HOME


@router.post("/bahasa", dependencies=[Depends(form_csrf)])
async def choose_language(request: Request, language: str = Form(...), back: str = Form(HOME)) -> Response:
    """The ID | EN switch: kept in the learner's session, so it holds on every page until they switch back."""
    if language in i18n.LANGUAGES:
        request.session["language"] = language
    return RedirectResponse(same_site_path(back), status_code=303)


@router.post("/web-vitals", status_code=204)
async def web_vitals(request: Request, vital: WebVital) -> Response:
    async with web(request).db.app.begin() as connection:
        await connection.execute(
            text("INSERT INTO app.web_vitals (page, metric, value) VALUES (:page, :metric, :value)"),
            {"page": vital.page, "metric": vital.metric, "value": vital.value},
        )
    return Response(status_code=204)
