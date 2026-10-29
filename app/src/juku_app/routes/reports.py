"""The learner's weekly report (Phase 2 AG1), with the citation markers kept out of their way."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from juku_app.routes.common import Page, page, render, web

CITATION_MARKER = re.compile(r"\s*\[ref:[^\]\s]+\]")
LATEST_REPORT = """
SELECT week_start, body, is_fallback FROM app.reports WHERE learner_id = :id ORDER BY week_start DESC LIMIT 1
"""

router = APIRouter()


@router.get("/laporan")
async def report_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    """The learner's latest weekly report (AG1), with the citation markers kept out of their way."""
    async with web(request).db.app.connect() as connection:
        latest = (await connection.execute(text(LATEST_REPORT), {"id": current.learner.id})).first()
    report = None
    if latest is not None:
        report = {"week_start": latest.week_start, "body": CITATION_MARKER.sub("", str(latest.body)).strip()}
    return render(request, "laporan.html", page=current, report=report)
