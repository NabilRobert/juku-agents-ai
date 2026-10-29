"""The pages anyone may open, and the app's own signals: the health check, the data notice, real-user timings."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from juku_app.routes.common import render, web

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


@router.post("/web-vitals", status_code=204)
async def web_vitals(request: Request, vital: WebVital) -> Response:
    async with web(request).db.app.begin() as connection:
        await connection.execute(
            text("INSERT INTO app.web_vitals (page, metric, value) VALUES (:page, :metric, :value)"),
            {"page": vital.page, "metric": vital.metric, "value": vital.value},
        )
    return Response(status_code=204)
