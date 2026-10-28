"""Every scheduled job records its start and end (ADR-014).

The "missed run" alert compares monitoring.job_runs with
monitoring.expected_jobs, so a job that never starts (no crontab, a dead
container) is noticed as surely as one that fails.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import func, insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_ops.tables import job_runs


@asynccontextmanager
async def recorded_run(engine: AsyncEngine, job: str) -> AsyncGenerator[None]:
    """Wrap a job: a `running` row now, then `succeeded`, or `failed` with the error's class name."""
    async with engine.begin() as connection:
        run_id = await connection.scalar(insert(job_runs).values(job=job, status="running").returning(job_runs.c.id))
    try:
        yield
    except Exception as exc:
        async with engine.begin() as connection:
            await connection.execute(
                update(job_runs)
                .where(job_runs.c.id == run_id)
                .values(status="failed", finished_at=func.now(), error_category=type(exc).__name__)
            )
        raise
    async with engine.begin() as connection:
        await connection.execute(
            update(job_runs).where(job_runs.c.id == run_id).values(status="succeeded", finished_at=func.now())
        )
