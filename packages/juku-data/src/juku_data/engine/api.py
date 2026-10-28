"""The learning engine's API (stub: the engine lands in the next commits)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.engine.models import (
    GradedAnswer,
    Learner,
    Mistakes,
    Plan,
    Progress,
    Quiz,
    QuizKind,
    ReadingSentences,
    RecentActivity,
    Recommendations,
)


@dataclass(frozen=True)
class Databases:
    """The app database (learner data) and the dict database (OpenJLPT); Postgres can't join across them."""

    app: AsyncEngine
    dictionary: AsyncEngine


class LearnerNotFoundError(LookupError):
    """No learner has this ID."""


class UnknownWordError(LookupError):
    """The word ID isn't in the dictionary."""


async def create_learner(
    db: Databases,
    *,
    nickname: str,
    target_level: int,
    timezone: str = "Asia/Jakarta",
    exam_date: date | None = None,
    cohort_id: int = 1,
    public_id: str | None = None,
) -> Learner:
    raise NotImplementedError


async def get_learner(db: Databases, public_id: str) -> Learner:
    raise NotImplementedError


async def set_target_level(db: Databases, learner_id: int, target_level: int) -> None:
    raise NotImplementedError


async def set_timezone(db: Databases, learner_id: int, timezone: str) -> None:
    raise NotImplementedError


async def mark_known(db: Databases, learner_id: int, word_id: str, at: datetime) -> None:
    raise NotImplementedError


async def unmark_known(db: Databases, learner_id: int, word_id: str, at: datetime) -> None:
    raise NotImplementedError


async def record_quiz_answer(
    db: Databases, learner_id: int, word_id: str, kind: QuizKind, is_correct: bool, at: datetime
) -> None:
    raise NotImplementedError


async def grade_answer(
    db: Databases, learner_id: int, word_id: str, kind: QuizKind, chosen: str, at: datetime
) -> GradedAnswer:
    raise NotImplementedError


async def record_sentence_read(db: Databases, learner_id: int, sentence_id: int, at: datetime) -> None:
    raise NotImplementedError


async def get_progress(db: Databases, learner_id: int) -> Progress:
    raise NotImplementedError


async def get_mistakes(db: Databases, learner_id: int, now: datetime) -> Mistakes:
    raise NotImplementedError


async def recommend_words(db: Databases, learner_id: int) -> Recommendations:
    raise NotImplementedError


async def find_reading_sentences(db: Databases, learner_id: int) -> ReadingSentences:
    raise NotImplementedError


async def get_plan(db: Databases, learner_id: int, today: date) -> Plan:
    raise NotImplementedError


async def get_recent_activity(db: Databases, learner_id: int, today: date, days: int = 7) -> RecentActivity:
    raise NotImplementedError


async def make_quiz(db: Databases, learner_id: int, today: date, batch: int = 0) -> Quiz:
    raise NotImplementedError


async def rebuild_learner(db: Databases, learner_id: int) -> None:
    raise NotImplementedError


async def verify_state(db: Databases, learner_ids: list[int] | None = None) -> list[str]:
    raise NotImplementedError
