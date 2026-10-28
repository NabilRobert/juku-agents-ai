"""The nightly memory consolidation (MEM-R4): every learner's active notes, kept or lapsed, with the reason.

Runs as the app's role, like the state check, because it recomputes each
learner's summaries and updates their notes. Recorded in monitoring.job_runs,
so the "missed run" alert notices if cron stops running it.
"""

from __future__ import annotations

from datetime import datetime

from juku_common.rules import Rules
from juku_data.memory import ConsolidationDecision, consolidate
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_ops.jobs import recorded_run

JOB_NAME = "consolidate-memory"
LEARNERS_WITH_NOTES = (
    "SELECT DISTINCT learner_id FROM learning.memory_notes WHERE status = 'active' ORDER BY learner_id"
)


async def consolidate_all(
    app: AsyncEngine, ops: AsyncEngine, rules: Rules, now: datetime
) -> list[ConsolidationDecision]:
    """Consolidate every learner who has an active note; the run is recorded, and fails as a whole if one fails."""
    decisions: list[ConsolidationDecision] = []
    async with recorded_run(ops, JOB_NAME):
        async with app.connect() as connection:
            learner_ids = [int(learner_id) for learner_id in await connection.scalars(text(LEARNERS_WITH_NOTES))]
        for learner_id in learner_ids:
            decisions += await consolidate(app, learner_id, rules, now)
    return decisions
