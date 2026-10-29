"""The run records (Phase 2 AG3): claiming a run, each draft and review, and the published report.

A weekly run is one row per (learner, week). Claiming it is idempotent
(FF7): a published week is skipped, a run another worker holds is left
alone until its lease runs out, and a run whose worker died is taken over.
Text (drafts, reviews, reports) expires like chat text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_app.chat import TEXT_RETENTION
from juku_app.pipeline.approval import Decision
from juku_app.pipeline.facts import WeekFacts
from juku_app.pipeline.outputs import Issue, Review

Claim = Literal["claimed", "done", "busy"]
FINISHED = ("published", "fallback")

NEW_WEEKLY_RUN = """
INSERT INTO app.pipeline_runs (learner_id, week_start, kind, status, started_at, claimed_at)
VALUES (:learner, :week, 'weekly', 'running', :now, :now)
ON CONFLICT (learner_id, week_start) WHERE kind = 'weekly' DO NOTHING
RETURNING id
"""
EXISTING_WEEKLY_RUN = """
SELECT id, status, claimed_at FROM app.pipeline_runs
WHERE learner_id = :learner AND week_start = :week AND kind = 'weekly' FOR UPDATE
"""
TAKE_OVER = "UPDATE app.pipeline_runs SET claimed_at = :now, attempts = attempts + 1 WHERE id = :id"
FINISH = "UPDATE app.pipeline_runs SET status = :status, finished_at = :now WHERE id = :id"


@dataclass(frozen=True)
class RunRef:
    """Which run a record belongs to: the run, its learner, and the week it's for."""

    run_id: int
    learner_id: int
    week: date


@dataclass(frozen=True)
class ReviewedDraft:
    """One attempt at an output: the draft, Tadashi's review, code's issues, and code's decision."""

    agent: str
    attempt: int
    content: Any
    review: Review | None
    code_issues: list[Issue]
    decision: Decision


@dataclass(frozen=True)
class ClaimedRun:
    run_id: int
    claim: Claim


async def claim_weekly_run(
    app: AsyncEngine, learner_id: int, week: date, now: datetime, lease: timedelta
) -> ClaimedRun:
    async with app.begin() as connection:
        created = await connection.scalar(text(NEW_WEEKLY_RUN), {"learner": learner_id, "week": week, "now": now})
        if created is not None:
            return ClaimedRun(int(created), "claimed")
        run_id, status, claimed_at = (
            await connection.execute(text(EXISTING_WEEKLY_RUN), {"learner": learner_id, "week": week})
        ).one()
        if status in FINISHED:
            return ClaimedRun(int(run_id), "done")
        if claimed_at is not None and now - claimed_at < lease:
            return ClaimedRun(int(run_id), "busy")
        await connection.execute(text(TAKE_OVER), {"now": now, "id": run_id})
    return ClaimedRun(int(run_id), "claimed")


async def start_replan_run(app: AsyncEngine, learner_id: int, week: date, request_id: int, now: datetime) -> int:
    async with app.begin() as connection:
        return int(
            await connection.scalar(
                text(
                    "INSERT INTO app.pipeline_runs (learner_id, week_start, kind, status, started_at, claimed_at, "
                    "replan_request_id) VALUES (:learner, :week, 'replan', 'running', :now, :now, :request) "
                    "RETURNING id"
                ),
                {"learner": learner_id, "week": week, "now": now, "request": request_id},
            )
        )


async def save_facts(app: AsyncEngine, run_id: int, facts: WeekFacts) -> None:
    async with app.begin() as connection:
        await connection.execute(
            text("UPDATE app.pipeline_runs SET facts = CAST(:facts AS jsonb) WHERE id = :id"),
            {"facts": facts.model_dump_json(), "id": run_id},
        )


async def record_review(app: AsyncEngine, run: RunRef, draft: ReviewedDraft, now: datetime) -> None:
    """One draft and its review, together: what the Run Inspector shows for each attempt."""
    expires = now + TEXT_RETENTION
    async with app.begin() as connection:
        output_id = await connection.scalar(
            text(
                "INSERT INTO app.agent_outputs (run_id, learner_id, agent, attempt, content, created_at, expires_at) "
                "VALUES (:run, :learner, :agent, :attempt, CAST(:content AS jsonb), :now, :expires) RETURNING id"
            ),
            {
                "run": run.run_id,
                "learner": run.learner_id,
                "agent": draft.agent,
                "attempt": draft.attempt,
                "content": json.dumps(draft.content, ensure_ascii=False),
                "now": now,
                "expires": expires,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO app.critic_reviews (run_id, learner_id, output_id, agent, grade, issues, code_issues, "
                "is_approved, reason, created_at, expires_at) VALUES (:run, :learner, :output, :agent, :grade, "
                "CAST(:issues AS jsonb), CAST(:code AS jsonb), :approved, :reason, :now, :expires)"
            ),
            {
                "run": run.run_id,
                "learner": run.learner_id,
                "output": output_id,
                "agent": draft.agent,
                "grade": draft.review.grade if draft.review else None,
                "issues": json.dumps([issue.model_dump() for issue in draft.review.issues] if draft.review else []),
                "code": json.dumps([issue.model_dump() for issue in draft.code_issues]),
                "approved": draft.decision.is_approved,
                "reason": draft.decision.reason,
                "now": now,
                "expires": expires,
            },
        )


async def publish_report(app: AsyncEngine, run: RunRef, body: str, is_fallback: bool, now: datetime) -> None:
    """The learner's report, once per week (a rerun can't add a second), and the run marked finished."""
    async with app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.reports (learner_id, run_id, week_start, body, is_fallback, created_at, expires_at) "
                "VALUES (:learner, :run, :week, :body, :fallback, :now, :expires) "
                "ON CONFLICT (learner_id, week_start) DO NOTHING"
            ),
            {
                "learner": run.learner_id,
                "run": run.run_id,
                "week": run.week,
                "body": body,
                "fallback": is_fallback,
                "now": now,
                "expires": now + TEXT_RETENTION,
            },
        )
        status = "fallback" if is_fallback else "published"
        await connection.execute(text(FINISH), {"status": status, "now": now, "id": run.run_id})


async def finish_run(app: AsyncEngine, run_id: int, status: str, now: datetime) -> None:
    async with app.begin() as connection:
        await connection.execute(text(FINISH), {"status": status, "now": now, "id": run_id})


async def record_skip(app: AsyncEngine, learner_id: int, week: date, reason: str, now: datetime) -> None:
    """A week skipped on purpose, and why: one row per (learner, week), updated if the job tries again."""
    async with app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.pipeline_skips (learner_id, week_start, reason, skipped_at) "
                "VALUES (:learner, :week, :reason, :now) ON CONFLICT (learner_id, week_start) "
                "DO UPDATE SET reason = excluded.reason, skipped_at = excluded.skipped_at"
            ),
            {"learner": learner_id, "week": week, "reason": reason, "now": now},
        )


async def clear_skip(app: AsyncEngine, learner_id: int, week: date) -> None:
    """The week's run goes ahead after all: the skip no longer accounts for it."""
    async with app.begin() as connection:
        await connection.execute(
            text("DELETE FROM app.pipeline_skips WHERE learner_id = :learner AND week_start = :week"),
            {"learner": learner_id, "week": week},
        )
