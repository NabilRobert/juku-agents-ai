"""Keiko's weekly curriculum check, as the pages see it (2026-11-05): queue one on a visit, show her latest note.

The weekly run (pipeline/run.py) writes the note; this module only asks for a run and reads the result. A
visit queues a check when the learner has had no weekly run in the last 7 days, which on the server means
Sunday's run was missed and on a laptop with no cron means every week; the hourly job takes the queue.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

CHECK_EVERY = timedelta(days=7)

QUEUE_IF_DUE = """
INSERT INTO app.check_requests (learner_id, requested_at)
SELECT :learner, :now
WHERE NOT EXISTS (
    SELECT 1 FROM app.pipeline_runs r
    WHERE r.learner_id = :learner AND r.kind = 'weekly' AND r.started_at > :since
)
ON CONFLICT (learner_id) DO NOTHING
"""
LATEST_NOTE = """
SELECT week_start, body FROM app.curriculum_notes WHERE learner_id = :learner ORDER BY week_start DESC LIMIT 1
"""
IS_QUEUED = "SELECT EXISTS (SELECT 1 FROM app.check_requests WHERE learner_id = :learner)"


class CurriculumNote(BaseModel):
    week_start: date
    body: str


async def queue_check_if_due(app: AsyncEngine, learner_id: int, now: datetime) -> None:
    async with app.begin() as connection:
        await connection.execute(text(QUEUE_IF_DUE), {"learner": learner_id, "now": now, "since": now - CHECK_EVERY})


async def latest_note(app: AsyncEngine, learner_id: int) -> CurriculumNote | None:
    async with app.connect() as connection:
        row = (await connection.execute(text(LATEST_NOTE), {"learner": learner_id})).first()
    return CurriculumNote(week_start=row.week_start, body=row.body) if row else None


async def is_check_queued(app: AsyncEngine, learner_id: int) -> bool:
    async with app.connect() as connection:
        return bool(await connection.scalar(text(IS_QUEUED), {"learner": learner_id}))
