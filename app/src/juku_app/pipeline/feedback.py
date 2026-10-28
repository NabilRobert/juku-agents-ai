"""Stub until the pipeline lands (EDD1): the weekly feedback job (AG4), which drafts and never applies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from juku_common.rules import Rules
from pydantic_ai.models import Model
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class FeedbackDraft:
    agent: str
    status: str
    text: str


async def draft_feedback(app: AsyncEngine, model: Model, rules: Rules, now: datetime) -> list[FeedbackDraft]:
    raise NotImplementedError
