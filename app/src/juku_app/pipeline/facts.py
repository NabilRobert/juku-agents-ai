"""The week's facts, gathered by code before any agent runs (ADR-007): everything an agent may state.

Agents are given these and nothing else they may claim. Each section is
citable by its name ([ref:activity]), and each word or note by its ID
([ref:<word_id>], [ref:note-12]); code checks every citation and every
number against them (juku_app.pipeline.checks). The week is Monday to
Sunday in the learner's own timezone.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from juku_data import engine
from juku_data.engine import Databases
from juku_data.engine.models import DayActivity, Learner, Mistakes, Plan, Progress, Recommendations
from juku_data.memory import Memory, get_memory
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

DAYS_IN_WEEK = 7


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
    """Monday and Sunday of the learner's local week that contains `now`."""
    local_day = now.astimezone(ZoneInfo(timezone)).date()
    start = local_day - timedelta(days=local_day.weekday())
    return start, start + timedelta(days=DAYS_IN_WEEK - 1)


async def gather_facts(db: Databases, learner: Learner, now: datetime) -> WeekFacts:
    week_start, week_end = week_of(now, learner.timezone)
    recent = await engine.get_recent_activity(db, learner.id, week_end, days=DAYS_IN_WEEK)
    days = [day for day in recent.days if week_start <= day.day <= week_end]
    activity = WeekActivity(
        quiz_answers=sum(day.quiz_answers for day in days),
        quiz_correct=sum(day.quiz_correct for day in days),
        words_marked=sum(day.words_marked for day in days),
        sentences_read=sum(day.sentences_read for day in days),
        days=days,
    )
    progress = await engine.get_progress(db, learner.id)
    return WeekFacts(
        week_start=week_start,
        week_end=week_end,
        target_level=progress.target_level,
        progress=progress,
        activity=activity,
        mistakes=await engine.get_mistakes(db, learner.id, now),
        candidates=await engine.recommend_words(db, learner.id),
        plan=await engine.get_plan(db, learner.id, now.astimezone(ZoneInfo(learner.timezone)).date()),
        memory=await get_memory(db, learner.id, now),
    )


async def retired_note_ids(db: Databases, learner_id: int) -> frozenset[str]:
    """The learner's notes no longer in use (removed, marked wrong, lapsed): never shown to agents, only checked."""
    async with db.app.connect() as connection:
        ids = await connection.scalars(
            text("SELECT id FROM learning.memory_notes WHERE learner_id = :learner AND status <> 'active'"),
            {"learner": learner_id},
        )
        return frozenset(f"note-{note_id}" for note_id in ids)
