"""Hapus data saya and Unduh data saya (stub: lands in the next commit)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine


async def delete_learner(engine: AsyncEngine, learner_id: int) -> dict[str, int]:
    raise NotImplementedError


async def export_learner(engine: AsyncEngine, learner_id: int) -> dict[str, Any]:
    raise NotImplementedError
