"""Stub until the memory slice's code lands (EDD1): the nightly consolidation of every learner's notes."""

from __future__ import annotations

from datetime import datetime

from juku_common.rules import Rules
from juku_data.memory import ConsolidationDecision
from sqlalchemy.ext.asyncio import AsyncEngine

JOB_NAME = "consolidate-memory"


async def consolidate_all(
    app: AsyncEngine, ops: AsyncEngine, rules: Rules, now: datetime
) -> list[ConsolidationDecision]:
    raise NotImplementedError
