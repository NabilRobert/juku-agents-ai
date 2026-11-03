"""The owner page (ADR-029): every learner, new invite codes, removing a learner, and the audit of each.

Behind the same guard as the Run Inspector (common.py: admin), so anyone
but the owner gets a 404. Making someone owner has no page on purpose:
it's `juku set-role`, on the server.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from juku_data.engine import LearnerNotFoundError
from juku_data.engine.models import Learner

from juku_app import owner
from juku_app.routes.common import admin, form_csrf, render, web

router = APIRouter()


def _as_owner(learner: Learner) -> owner.Actor:
    return owner.Actor(place="page", owner_id=learner.id)


async def _show(request: Request, status_code: int = 200, **shown: Any) -> HTMLResponse:
    learners, actions = await owner.learners_and_actions(web(request).db.app)
    response = render(
        request, "admin_learners.html", learners=learners, actions=actions, max_codes=owner.MAX_CODES_AT_ONCE, **shown
    )
    response.status_code = status_code
    return response


@router.get("/admin/learners", dependencies=[Depends(admin)])
async def learners_page(request: Request) -> HTMLResponse:
    return await _show(request)


@router.post("/admin/learners/codes", dependencies=[Depends(form_csrf)])
async def issue_codes(
    request: Request,
    current: Learner = Depends(admin),  # noqa: B008
    count: int = Form(1),
) -> HTMLResponse:
    """New codes, shown on this response only: only their hashes are kept."""
    try:
        codes = await owner.issue_codes(web(request).db.app, _as_owner(current), count)
    except owner.OwnerActionRefusedError as refused:
        return await _show(request, status_code=400, error=str(refused))
    return await _show(request, new_codes=codes)


@router.post("/admin/learners/remove", dependencies=[Depends(form_csrf)])
async def remove_learner(
    request: Request,
    current: Learner = Depends(admin),  # noqa: B008
    public_id: str = Form(...),
    confirm: str = Form(""),
) -> HTMLResponse:
    """Delete one learner's data; the owner types the learner's public ID to confirm."""
    if confirm.strip() != public_id:
        return await _show(request, status_code=400, error=f"Type {public_id} to confirm removing that learner.")
    try:
        removed = await owner.remove_learner(web(request).db.app, _as_owner(current), public_id)
    except (owner.OwnerActionRefusedError, LearnerNotFoundError) as refused:
        return await _show(request, status_code=400, error=str(refused))
    return await _show(request, removed=public_id, removed_rows=sum(removed.values()))
