"""This week on Home, Monday to Sunday: each day's lesson done against the day's target. Summaries only (FF2), $0.

A day's target is today's lesson (engine/curriculum.py: today_plan): the day's words, the quiz, the sentences
and the grammar point. Past days are measured against today's target too, because the pace behind the words
target comes from the plan, which is recomputed each day and not kept. Each part counts up to its own target,
so fifty quiz answers don't make up for no words.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.engine.curriculum_models import TodayPlan, WeekDay
from juku_data.engine.models import DayActivity, Learner
from juku_data.engine.reads import get_recent_activity
from juku_data.engine.recompute import GRAMMAR_STUDIED

DAYS_IN_WEEK = 7
GRAMMAR_SINCE = (
    "SELECT first_at FROM learning.learner_studied WHERE learner_id = :learner AND kind = :kind AND first_at >= :since"
)


def _part_targets(plan: TodayPlan) -> tuple[int, int, int, int]:
    """Words, quiz answers, sentences and grammar points a day; no grammar target once the unit has none left."""
    has_grammar = plan.grammar is not None or plan.grammar_done > 0
    return plan.words_target, plan.quiz_target, plan.sentences_target, 1 if has_grammar else 0


def _day_done(activity: DayActivity | None, grammar: int, targets: tuple[int, int, int, int]) -> int:
    if activity is None:
        parts = (0, 0, 0, grammar)
    else:
        parts = (activity.words_marked, activity.quiz_answers, activity.sentences_read, grammar)
    return sum(min(part, target) for part, target in zip(parts, targets, strict=True))


async def _grammar_per_day(app: AsyncEngine, learner: Learner, monday: date) -> dict[date, int]:
    zone = ZoneInfo(learner.timezone)
    since = datetime.combine(monday, time(), zone)
    async with app.connect() as connection:
        times = await connection.scalars(
            text(GRAMMAR_SINCE), {"learner": learner.id, "kind": GRAMMAR_STUDIED, "since": since}
        )
        per_day: dict[date, int] = {}
        for at in times:
            day = at.astimezone(zone).date()
            per_day[day] = per_day.get(day, 0) + 1
    return per_day


async def week_days(app: AsyncEngine, learner: Learner, plan: TodayPlan, today: date) -> list[WeekDay]:
    """Monday to Sunday of today's week; days after today have nothing done yet."""
    monday = today - timedelta(days=today.weekday())
    recent = await get_recent_activity(app, learner.id, today, days=today.weekday() + 1)
    by_day = {activity.day: activity for activity in recent.days}
    grammar = await _grammar_per_day(app, learner, monday)
    targets = _part_targets(plan)
    week: list[WeekDay] = []
    for offset in range(DAYS_IN_WEEK):
        day = monday + timedelta(days=offset)
        done = _day_done(by_day.get(day), grammar.get(day, 0), targets)
        week.append(WeekDay(day=day, done=done, target=sum(targets), is_future=day > today))
    return week
