"""FF3 in production: every night, every learner's summaries against a recompute from their events.

The summaries are what pages and agents read; the events are the source
of truth. If they drift apart (a bug in an incremental update, a manual
edit), this job fails, its run is recorded as failed, and the "a job
failed" alert fires. The differences printed name internal IDs, item IDs
and counts only, never content.
"""

from __future__ import annotations

from juku_data.engine.recompute import verify_learners
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_ops.jobs import recorded_run

JOB_NAME = "verify-state"


class StateDriftError(Exception):
    """The summaries differ from a recompute from the events."""


async def verify_production_state(app: AsyncEngine, ops: AsyncEngine) -> list[str]:
    """Run the check as a recorded job; raises StateDriftError (recorded as failed) if anything differs."""
    async with recorded_run(ops, JOB_NAME):
        async with app.begin() as connection:
            differences = await verify_learners(connection)
        if differences:
            raise StateDriftError(f"{len(differences)} differences between the summaries and a recompute")
    return differences
