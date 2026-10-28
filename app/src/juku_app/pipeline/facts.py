"""Stub until the pipeline lands (EDD1): the week's facts, gathered by code before any agent runs."""

from __future__ import annotations

from datetime import date, datetime

from juku_data.engine import Databases
from juku_data.engine.models import DayActivity, Learner, Mistakes, Plan, Progress, Recommendations
from juku_data.memory import Memory
from pydantic import BaseModel, ConfigDict


class WeekActivity(BaseModel):
    model_config = ConfigDict(frozen=True)

    quiz_answers: int
    quiz_correct: int
    words_marked: int
    sentences_read: int
    days: list[DayActivity]


class WeekFacts(BaseModel):
    """Everything an agent may state, each section citable by its name ([ref:activity]) and each item by its ID."""

    model_config = ConfigDict(frozen=True)

    week_start: date
    week_end: date
    target_level: int
    progress: Progress
    activity: WeekActivity
    mistakes: Mistakes
    candidates: Recommendations
    plan: Plan
    memory: Memory


def week_of(now: datetime, timezone: str) -> tuple[date, date]:
    raise NotImplementedError


async def gather_facts(db: Databases, learner: Learner, now: datetime) -> WeekFacts:
    raise NotImplementedError
