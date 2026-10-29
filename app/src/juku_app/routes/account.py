"""A learner's first visit and sign-in (Phase 2 UI1): an invite code, the consent notice, then their details.

/masuk takes the invite code; a new one goes on to the consent notice
(/persetujuan), then the learner's nickname, level, timezone and exam
date (/mulai). A returning learner on an older notice is asked again.
"""

from __future__ import annotations

from datetime import date
from typing import cast

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from juku_data import engine
from sqlalchemy import text

from juku_app.consent import CONSENT_VERSION, ConsentAnswers, ConsentRefusedError, has_current_consent, record_consent
from juku_app.invites import Invite, InviteRefusedError, attach, redeem
from juku_app.routes.common import LEVELS, TIMEZONES, Redirect, form_csrf, render, web

router = APIRouter()


def pending_invite(request: Request) -> int | None:
    value = request.session.get("invite")
    return value if isinstance(value, int) else None


@router.get("/")
async def root() -> Response:
    return RedirectResponse("/beranda", status_code=303)


@router.get("/masuk")
async def sign_in_form(request: Request) -> HTMLResponse:
    return render(request, "masuk.html")


@router.post("/masuk", dependencies=[Depends(form_csrf)])
async def sign_in(request: Request, code: str = Form("")) -> Response:
    db = web(request).db
    try:
        invite = await redeem(db.app, code)
    except InviteRefusedError:
        return render(request, "masuk.html", error=True)
    if invite.learner_id is None:
        request.session["invite"] = invite.id
        return RedirectResponse("/persetujuan", status_code=303)
    async with db.app.connect() as connection:
        public_id = await connection.scalar(
            text("SELECT public_id FROM learning.learners WHERE id = :id"), {"id": invite.learner_id}
        )
    request.session["learner"] = str(public_id)
    location = "/beranda" if await has_current_consent(db.app, invite.learner_id) else "/persetujuan"
    return RedirectResponse(location, status_code=303)


@router.get("/persetujuan")
async def consent_form(request: Request) -> Response:
    if pending_invite(request) is None and "learner" not in request.session:
        raise Redirect("/masuk")
    return render(request, "persetujuan.html", version=CONSENT_VERSION)


@router.post("/persetujuan", dependencies=[Depends(form_csrf)])
async def consent(
    request: Request,
    is_adult: str = Form(""),
    accepts_service: str = Form(""),
    accepts_aggregates: str = Form(""),
    accepts_group_digest: str = Form(""),
) -> Response:
    answers = ConsentAnswers(
        is_adult=bool(is_adult),
        accepts_service=bool(accepts_service),
        accepts_aggregates=bool(accepts_aggregates),
        accepts_group_digest=bool(accepts_group_digest),
    )
    if not (answers.is_adult and answers.accepts_service):
        return render(request, "persetujuan.html", version=CONSENT_VERSION, error=True)
    db = web(request).db
    public_id = request.session.get("learner")
    if isinstance(public_id, str):  # a returning learner, asked again for a new version
        learner = await engine.get_learner(db, public_id)
        await record_consent(db.app, learner.id, answers)
        return RedirectResponse("/beranda", status_code=303)
    if pending_invite(request) is None:
        raise Redirect("/masuk")
    request.session["consent"] = answers.__dict__
    return RedirectResponse("/mulai", status_code=303)


@router.get("/mulai")
async def start_form(request: Request) -> Response:
    if pending_invite(request) is None or "consent" not in request.session:
        raise Redirect("/masuk")
    return render(request, "mulai.html", timezones=TIMEZONES, levels=LEVELS)


@router.post("/mulai", dependencies=[Depends(form_csrf)])
async def start(
    request: Request,
    nickname: str = Form(..., min_length=1, max_length=30),
    target_level: int = Form(5),
    timezone: str = Form("Asia/Jakarta"),
    exam_date: str = Form(""),
) -> Response:
    invite_id, answers = pending_invite(request), request.session.get("consent")
    if invite_id is None or not isinstance(answers, dict):
        raise Redirect("/masuk")
    db = web(request).db
    learner = await engine.create_learner(
        db,
        nickname=nickname.strip(),
        target_level=target_level,
        timezone=timezone,
        exam_date=date.fromisoformat(exam_date) if exam_date else None,
    )
    await attach(db.app, Invite(id=invite_id, learner_id=None), learner.id)
    try:
        await record_consent(db.app, learner.id, ConsentAnswers(**cast(dict[str, bool], answers)))
    except ConsentRefusedError:
        raise Redirect("/persetujuan") from None
    request.session.pop("invite", None)
    request.session.pop("consent", None)
    request.session["learner"] = learner.public_id
    return RedirectResponse("/beranda", status_code=303)
