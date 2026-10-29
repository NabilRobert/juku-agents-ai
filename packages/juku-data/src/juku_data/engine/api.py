"""The learning engine's public functions: what the MCP server, the app and the CLI call.

Each takes `Databases` and an internal learner ID (Juku's MCP server
resolves the ID from the verified token's public ID first, never from a
tool argument). Reads return typed models; writes run in one transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.engine import quiz, reads, writes
from juku_data.engine.models import (
    GradedAnswer,
    KnownWords,
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
from juku_data.engine.recompute import MARKED_KNOWN, UNMARKED_KNOWN, rebuild_learners, verify_learners
from juku_data.engine.writes import LearnerNotFoundError, UnknownWordError

RECENT_ACTIVITY_DAYS = 7
# The memory page lists this many known words, latest first; the rest are counted.
KNOWN_WORDS_SHOWN = 50

__all__ = ["LearnerNotFoundError", "UnknownWordError"]


@dataclass(frozen=True)
class Databases:
    """The app database (learner data) and the dict database (OpenJLPT); Postgres can't join across them."""

    app: AsyncEngine
    dictionary: AsyncEngine


async def create_learner(  # noqa: PLR0913 (keyword-only: the learner's own fields)
    db: Databases,
    *,
    nickname: str,
    target_level: int,
    timezone: str = "Asia/Jakarta",
    exam_date: date | None = None,
    cohort_id: int = 1,
    public_id: str | None = None,
) -> Learner:
    """A new learner, with a random public ID unless one is given (fixtures and the synthetic database)."""
    async with db.app.begin() as connection:
        return await writes.create_learner(
            connection,
            nickname=nickname,
            target_level=target_level,
            timezone=timezone,
            exam_date=exam_date,
            cohort_id=cohort_id,
            public_id=public_id,
        )


async def get_learner(db: Databases, public_id: str) -> Learner:
    async with db.app.connect() as connection:
        return await writes.find_learner(connection, public_id)


async def set_target_level(db: Databases, learner_id: int, target_level: int) -> None:
    async with db.app.begin() as connection:
        await writes.update_learner(connection, learner_id, target_level=target_level)


async def set_timezone(db: Databases, learner_id: int, timezone: str) -> None:
    async with db.app.begin() as connection:
        await writes.update_learner(connection, learner_id, timezone=timezone)


async def mark_known(db: Databases, learner_id: int, word_id: str, at: datetime) -> None:
    """The learner's own click (LE1): never an agent's (SM4)."""
    await writes.check_word(db.dictionary, word_id)
    async with db.app.begin() as connection:
        await writes.apply_word_event(connection, learner_id, word_id, MARKED_KNOWN, at)


async def unmark_known(db: Databases, learner_id: int, word_id: str, at: datetime) -> None:
    await writes.check_word(db.dictionary, word_id)
    async with db.app.begin() as connection:
        await writes.apply_word_event(connection, learner_id, word_id, UNMARKED_KNOWN, at)


async def record_quiz_answer(  # noqa: PLR0913 (one quiz answer's fields; the engine's public API)
    db: Databases, learner_id: int, word_id: str, kind: QuizKind, is_correct: bool, at: datetime
) -> None:
    await writes.check_word(db.dictionary, word_id)
    async with db.app.begin() as connection:
        await writes.apply_word_event(
            connection, learner_id, word_id, writes.QUIZ_EVENT[kind], at, is_correct=is_correct
        )


async def grade_answer(  # noqa: PLR0913 (one quiz answer's fields; the engine's public API)
    db: Databases, learner_id: int, word_id: str, kind: QuizKind, chosen: str, at: datetime
) -> GradedAnswer:
    """LE2: grade against the answer looked up again, then record it."""
    correct = await quiz.correct_option(db.dictionary, word_id, kind)
    if correct is None:
        raise UnknownWordError(f"{word_id!r} isn't a quizzable word")
    result = quiz.graded(word_id, kind, chosen, correct)
    await record_quiz_answer(db, learner_id, word_id, kind, result.is_correct, at)
    return result


async def record_sentence_read(db: Databases, learner_id: int, sentence_id: int, at: datetime) -> None:
    async with db.app.begin() as connection:
        await writes.apply_sentence_read(connection, learner_id, sentence_id, at)


async def get_progress(db: Databases, learner_id: int) -> Progress:
    return await reads.get_progress(db.app, learner_id)


async def get_mistakes(db: Databases, learner_id: int, now: datetime) -> Mistakes:
    return await reads.get_mistakes(db.app, db.dictionary, learner_id, now)


async def recommend_words(db: Databases, learner_id: int) -> Recommendations:
    return await reads.recommend_words(db.app, db.dictionary, learner_id)


async def find_reading_sentences(db: Databases, learner_id: int) -> ReadingSentences:
    return await reads.find_reading_sentences(db.app, db.dictionary, learner_id)


async def get_plan(db: Databases, learner_id: int, today: date) -> Plan:
    async with db.app.connect() as connection:
        learner = await writes.load_learner(connection, learner_id)
    return await reads.get_plan(db.app, learner, today)


async def get_known_words(db: Databases, learner_id: int, limit: int = KNOWN_WORDS_SHOWN) -> KnownWords:
    return await reads.get_known_words(db.app, db.dictionary, learner_id, limit)


async def get_recent_activity(
    db: Databases, learner_id: int, today: date, days: int = RECENT_ACTIVITY_DAYS
) -> RecentActivity:
    return await reads.get_recent_activity(db.app, learner_id, today, days)


async def make_quiz(db: Databases, learner_id: int, today: date, batch: int = 0) -> Quiz:
    async with db.app.connect() as connection:
        learner = await writes.load_learner(connection, learner_id)
    return await quiz.make_quiz(db.app, db.dictionary, learner, today, batch)


async def rebuild_learner(db: Databases, learner_id: int) -> None:
    """Replace the learner's summaries with a recompute from their events."""
    async with db.app.begin() as connection:
        await writes.lock_learner(connection, learner_id)
        await rebuild_learners(connection, [learner_id])


async def verify_state(db: Databases, learner_ids: list[int] | None = None) -> list[str]:
    """FF3: every difference between the summaries and a recompute (all learners if none are named)."""
    async with db.app.begin() as connection:
        return await verify_learners(connection, learner_ids)
