"""The dead-man's switch (Phase 2 M5): a beat only while the app answers.

Cron runs `juku-ops heartbeat` every minute inside the app's container. It
asks the app's health endpoint and, only if that answers 200, records the
beat. Grafana alerts when the latest beat is more than 5 minutes old, which
catches a dead app, a dead container and a missing crontab alike.
"""

from __future__ import annotations

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_ops.tables import heartbeats

HEALTH_TIMEOUT_SECONDS = 5.0
HTTP_OK = 200


async def is_healthy(client: httpx.AsyncClient, url: str) -> bool:
    try:
        response = await client.get(url, timeout=HEALTH_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        return False
    return response.status_code == HTTP_OK


async def beat(engine: AsyncEngine, source: str) -> None:
    """Record that `source` is alive now."""
    statement = insert(heartbeats).values(source=source, beat_at=func.now())
    statement = statement.on_conflict_do_update(
        index_elements=[heartbeats.c.source], set_={"beat_at": statement.excluded.beat_at}
    )
    async with engine.begin() as connection:
        await connection.execute(statement)
