"""The Run Inspector (Phase 2 AG3), for Arthur only: the latest runs, one run in full, and the feedback drafts."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from juku_app.routes.common import admin, web

# Enough to see the week, small enough to load at once.
INSPECTOR_ROWS = 50
LATEST_RUNS = """
SELECT r.id, l.public_id, r.week_start, r.kind, r.status, r.attempts, r.started_at, r.finished_at
FROM app.pipeline_runs r JOIN learning.learners l ON l.id = r.learner_id ORDER BY r.id DESC LIMIT :limit
"""
LATEST_DRAFTS = (
    "SELECT week_start, agent, patterns, draft, status FROM app.prompt_feedback ORDER BY id DESC LIMIT :limit"
)
ONE_RUN = """
SELECT r.id, l.public_id, r.week_start, r.kind, r.status, r.attempts, r.started_at, r.finished_at, r.facts
FROM app.pipeline_runs r JOIN learning.learners l ON l.id = r.learner_id WHERE r.id = :id
"""
RUN_ATTEMPTS = """
SELECT o.agent, o.attempt, o.content, c.grade, c.issues, c.code_issues, c.is_approved, c.reason
FROM app.agent_outputs o JOIN app.critic_reviews c ON c.output_id = o.id WHERE o.run_id = :id ORDER BY o.id
"""
RUN_REPORT = "SELECT body, is_fallback FROM app.reports WHERE run_id = :id"

router = APIRouter()


@router.get("/admin/runs", dependencies=[Depends(admin)])
async def admin_runs(request: Request) -> HTMLResponse:
    """The Run Inspector's index (AG3): the latest runs, and the feedback job's drafts (AG4)."""
    context = web(request)
    async with context.db.app.connect() as connection:
        runs = (await connection.execute(text(LATEST_RUNS), {"limit": INSPECTOR_ROWS})).mappings().all()
        drafts = (await connection.execute(text(LATEST_DRAFTS), {"limit": INSPECTOR_ROWS})).mappings().all()
    return context.views.TemplateResponse(request, "admin_runs.html", {"runs": runs, "drafts": drafts})


@router.get("/admin/runs/{run_id}", dependencies=[Depends(admin)])
async def admin_run(request: Request, run_id: int) -> HTMLResponse:
    """One run: its facts, every draft, every review with code's issues, the decision, the report."""
    context = web(request)
    async with context.db.app.connect() as connection:
        run = (await connection.execute(text(ONE_RUN), {"id": run_id})).mappings().first()
        if run is None:
            raise HTTPException(status_code=404)
        attempts = (await connection.execute(text(RUN_ATTEMPTS), {"id": run_id})).mappings().all()
        report = (await connection.execute(text(RUN_REPORT), {"id": run_id})).mappings().first()
    shown = {"run": run, "facts": json.dumps(run["facts"], ensure_ascii=False, indent=1), "attempts": attempts}
    return context.views.TemplateResponse(request, "admin_run.html", {**shown, "report": report})
