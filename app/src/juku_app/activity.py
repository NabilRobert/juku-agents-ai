"""The activity calendar on the home page (Arthur, 2026-11-05): how much a learner did each day, like GitHub's.

A day's count is the learner's own actions that day, in their own timezone: quiz answers, words marked
known, sentences read (the engine's daily summaries, never the event log: FF2), and questions asked to
Shiori. $0, and only ever the signed-in learner's own days: the learner ID comes from their session.
"""

from __future__ import annotations

from datetime import date, timedelta

from juku_data import engine
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from pydantic import BaseModel
from sqlalchemy import text

# Half a year: 26 week columns still fit a phone's width.
CALENDAR_WEEKS = 26
CALENDAR_DAYS = CALENDAR_WEEKS * 7
QUESTIONS_PER_DAY = """
SELECT (created_at AT TIME ZONE :timezone)::date AS day, count(*) AS questions
FROM app.chat_messages
WHERE learner_id = :learner AND role = 'learner' AND created_at AT TIME ZONE :timezone >= :since
GROUP BY 1
"""


class ActiveDay(BaseModel):
    day: date
    count: int
    quiz_answers: int
    words_marked: int
    sentences_read: int
    questions: int


async def _questions_per_day(db: Databases, learner: Learner, since: date) -> dict[date, int]:
    async with db.app.connect() as connection:
        rows = await connection.execute(
            text(QUESTIONS_PER_DAY), {"learner": learner.id, "timezone": learner.timezone, "since": since}
        )
        return {row.day: int(row.questions) for row in rows}


async def active_days(db: Databases, learner: Learner, today: date) -> list[ActiveDay]:
    """Every day with any activity in the calendar's half year, oldest first; a day with none isn't listed."""
    recent = await engine.get_recent_activity(db, learner.id, today, days=CALENDAR_DAYS)
    questions = await _questions_per_day(db, learner, today - timedelta(days=CALENDAR_DAYS - 1))
    by_day = {activity.day: activity for activity in recent.days}
    days: list[ActiveDay] = []
    for day in sorted(set(by_day) | set(questions)):
        activity = by_day.get(day)
        answers = activity.quiz_answers if activity else 0
        marked = activity.words_marked if activity else 0
        read = activity.sentences_read if activity else 0
        asked = questions.get(day, 0)
        count = answers + marked + read + asked
        if count:
            days.append(
                ActiveDay(
                    day=day,
                    count=count,
                    quiz_answers=answers,
                    words_marked=marked,
                    sentences_read=read,
                    questions=asked,
                )
            )
    return days
