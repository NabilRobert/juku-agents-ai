"""Stub until the pipeline lands (EDD1): one learner's weekly run, idempotent per (learner, week)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from pydantic import BaseModel

from juku_app.budget import BudgetGuard
from juku_app.pipeline.crew import Crew

RunStatus = Literal["published", "fallback", "skipped", "replanned", "busy"]


@dataclass(frozen=True)
class PipelineServices:
    db: Databases
    rules: Rules
    guard: BudgetGuard
    signer: Signer
    crew: Crew


class RunOutcome(BaseModel):
    run_id: int | None
    status: RunStatus
    report: str | None = None


async def run_weekly(services: PipelineServices, learner: Learner, now: datetime) -> RunOutcome:
    raise NotImplementedError
