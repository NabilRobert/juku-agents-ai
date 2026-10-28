"""The budget guard (B1, B2) (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from juku_common.rules import Rules
from pydantic_ai.usage import RunUsage, UsageLimits
from sqlalchemy.ext.asyncio import AsyncEngine

Pool = Literal["chat", "reports"]


class BudgetRefusedError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class BudgetGuard:
    engine: AsyncEngine
    rules: Rules

    def cost_of(self, usage: RunUsage) -> Decimal:
        raise NotImplementedError

    def run_limits(self, pool: Pool) -> UsageLimits:
        raise NotImplementedError

    async def check(self, pool: Pool, learner_id: int | None, now: datetime) -> None:
        raise NotImplementedError

    async def record(self, pool: Pool, learner_id: int | None, usage: RunUsage) -> Decimal:
        raise NotImplementedError

    async def sync_pool_sizes(self) -> None:
        raise NotImplementedError
