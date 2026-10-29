"""The learner's settings and their data rights (Phase 2, privacy): change details, download, delete."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from juku_data import engine
from sqlalchemy import text

from juku_app import privacy
from juku_app.routes.common import LEVELS, TIMEZONES, Page, form_csrf, page, render, web

DELETE_CONFIRMATION = "HAPUS"

router = APIRouter()


@router.get("/pengaturan")
async def settings_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    return render(request, "pengaturan.html", page=current, timezones=TIMEZONES, levels=LEVELS)


@router.post("/pengaturan", dependencies=[Depends(form_csrf)])
async def update_settings(
    request: Request,
    current: Page = Depends(page),  # noqa: B008
    target_level: int = Form(...),
    timezone: str = Form(...),
    exam_date: str = Form(""),
) -> Response:
    db = web(request).db
    if target_level != current.learner.target_level:
        await engine.set_target_level(db, current.learner.id, target_level)
    if timezone != current.learner.timezone:
        await engine.set_timezone(db, current.learner.id, timezone)
    async with db.app.begin() as connection:
        await connection.execute(
            text("UPDATE learning.learners SET exam_date = :exam WHERE id = :id"),
            {"exam": date.fromisoformat(exam_date) if exam_date else None, "id": current.learner.id},
        )
    return RedirectResponse("/pengaturan", status_code=303)


@router.get("/unduh-data")
async def download(request: Request, current: Page = Depends(page)) -> Response:  # noqa: B008
    exported = await privacy.export_learner(web(request).db.app, current.learner.id)
    return Response(
        json.dumps(exported, ensure_ascii=False, indent=1),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="juku-data-saya.json"'},
    )


@router.post("/hapus-data", dependencies=[Depends(form_csrf)])
async def delete(request: Request, current: Page = Depends(page), confirm: str = Form("")) -> Response:  # noqa: B008
    if confirm.strip().upper() != DELETE_CONFIRMATION:
        return render(request, "pengaturan.html", page=current, timezones=TIMEZONES, levels=LEVELS, delete_error=True)
    await privacy.delete_learner(web(request).db.app, current.learner.id)
    request.session.clear()
    return render(request, "hapus_selesai.html")
