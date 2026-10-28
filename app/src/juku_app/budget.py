"""The budget guard (ADR-012; Phase 2 B1, B2), checked before every model call.

Two pools, sized in guardrails.yaml's `budget` section:
- **reports** are reserved, so a busy week of chat can't cancel anyone's
  weekly report;
- **chat** has a hard stop when its pool is spent, a global daily cap,
  and a cap on each learner's questions per day (their local day).

`check` runs before a run and raises with a reason the learner is told in
plain words; the $0 features keep working. Each run is also capped by
PydanticAI's `UsageLimits` (`run_limits`), so one runaway loop can't spend
a day's budget. `record` writes the run's tokens and cost afterwards,
priced from the committed table; cached input is priced as fresh input, so
the recorded cost errs high (B2). The provider's key cap is the backstop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import ROUND_CEILING, Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from juku_common.rules import Rules
from pydantic_ai.usage import RunUsage, UsageLimits
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

Pool = Literal["chat", "reports"]
MILLION = Decimal(1_000_000)
# Costs are kept to the millionth of a dollar, rounded up.
COST_STEP = Decimal("0.000001")

POOL_SPENT = "SELECT coalesce(sum(cost_usd), 0) FROM app.model_calls WHERE pool = :pool"
SPENT_SINCE = "SELECT coalesce(sum(cost_usd), 0) FROM app.model_calls WHERE pool = 'chat' AND called_at >= :since"
QUESTIONS_SINCE = (
    "SELECT count(*) FROM app.model_calls WHERE pool = 'chat' AND learner_id = :learner AND called_at >= :since"
)
LEARNER_TIMEZONE = "SELECT timezone FROM learning.learners WHERE id = :learner"


class BudgetRefusedError(Exception):
    """No model call: a cap is reached. `reason` names which; the message is for the learner's page."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def start_of_day(now: datetime, timezone: str) -> datetime:
    """Midnight of `now`'s date in `timezone`."""
    local = now.astimezone(ZoneInfo(timezone))
    return datetime.combine(local.date(), time(), tzinfo=ZoneInfo(timezone))


@dataclass(frozen=True)
class BudgetGuard:
    engine: AsyncEngine
    rules: Rules

    def cost_of(self, usage: RunUsage) -> Decimal:
        prices = self.rules.budget
        cost = (
            Decimal(usage.input_tokens) * Decimal(str(prices.input_usd_per_million))
            + Decimal(usage.output_tokens) * Decimal(str(prices.output_usd_per_million))
        ) / MILLION
        return cost.quantize(COST_STEP, rounding=ROUND_CEILING)

    def run_limits(self, pool: Pool) -> UsageLimits:
        budget = self.rules.budget
        if pool == "chat":
            return UsageLimits(
                request_limit=budget.chat_run_request_limit, total_tokens_limit=budget.chat_run_total_tokens_limit
            )
        return UsageLimits(
            request_limit=budget.report_run_request_limit, total_tokens_limit=budget.report_run_total_tokens_limit
        )

    async def check(self, pool: Pool, learner_id: int | None, now: datetime) -> None:
        """Raise BudgetRefusedError if a call in this pool, for this learner, would pass a cap."""
        budget = self.rules.budget
        async with self.engine.connect() as connection:
            spent = Decimal(await connection.scalar(text(POOL_SPENT), {"pool": pool}))
            if pool == "reports":
                if spent >= Decimal(str(budget.reports_pool_usd)):
                    raise BudgetRefusedError("reports_pool_spent", "The reports pool is spent.")
                return
            if spent >= Decimal(str(budget.chat_pool_usd)):
                raise BudgetRefusedError("chat_pool_spent", "Shiori sudah mencapai batas anggaran untuk periode ini.")
            today_utc = start_of_day(now, "UTC")
            spent_today = Decimal(await connection.scalar(text(SPENT_SINCE), {"since": today_utc}))
            if spent_today >= Decimal(str(budget.chat_daily_global_usd)):
                raise BudgetRefusedError("chat_daily_global", "Shiori sudah mencapai batas hari ini. Coba lagi besok.")
            if learner_id is None:
                return
            timezone = await connection.scalar(text(LEARNER_TIMEZONE), {"learner": learner_id})
            since = start_of_day(now, str(timezone or "UTC"))
            asked = int(await connection.scalar(text(QUESTIONS_SINCE), {"learner": learner_id, "since": since}) or 0)
            if asked >= budget.chat_daily_questions_per_learner:
                raise BudgetRefusedError(
                    "learner_daily_questions", "Kamu sudah bertanya cukup banyak hari ini. Coba lagi besok."
                )

    async def record(self, pool: Pool, learner_id: int | None, usage: RunUsage) -> Decimal:
        """Write one run's tokens and cost; return the cost."""
        cost = self.cost_of(usage)
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO app.model_calls (called_at, pool, learner_id, requests, input_tokens, "
                    "cached_input_tokens, output_tokens, cost_usd) "
                    "VALUES (:at, :pool, :learner, :requests, :input, :cached, :output, :cost)"
                ),
                {
                    "at": datetime.now(UTC),
                    "pool": pool,
                    "learner": learner_id,
                    "requests": usage.requests,
                    "input": usage.input_tokens,
                    "cached": usage.cache_read_tokens,
                    "output": usage.output_tokens,
                    "cost": cost,
                },
            )
        return cost

    async def sync_pool_sizes(self) -> None:
        """Copy the pools' sizes from the rule file for Grafana's budget alerts (run at every start-up)."""
        sizes = {"chat": self.rules.budget.chat_pool_usd, "reports": self.rules.budget.reports_pool_usd}
        async with self.engine.begin() as connection:
            for pool, size in sizes.items():
                await connection.execute(
                    text(
                        "INSERT INTO app.budget_pools (pool, size_usd) VALUES (:pool, :size) "
                        "ON CONFLICT (pool) DO UPDATE SET size_usd = excluded.size_usd"
                    ),
                    {"pool": pool, "size": Decimal(str(size))},
                )
