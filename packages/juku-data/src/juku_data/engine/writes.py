"""The engine's write side: learners, and events applied to the summaries as they arrive.

Each write runs in one transaction that first locks the learner's row, so
two tabs answering at once can't interleave their updates. An event is
appended to `learning_events` (the source of truth) and the summaries are
updated incrementally with engine/state.py's rules:
- the word's own row in `learner_state`;
- if the word became known or unknown: its kanji in `learner_kanji`, the
  level counts in `learner_coverage`, and the recommender's candidates for
  the words that share a kanji with it (`learner_candidate`);
- the day's counts in `learner_daily_activity`, by the learner's local date.
"""

from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_data.engine.models import Learner
from juku_data.engine.recompute import (
    MARKED_KNOWN,
    QUIZ_MEANING,
    QUIZ_READING,
    SENTENCE_READ,
    UNMARKED_KNOWN,
    candidate_query,
    rebuild_learners,
)
from juku_data.engine.state import ItemState, after_marked_known, after_quiz_answer, after_unmarked_known

# Juku serves N5 to N2 (Phase 2, core scenario); OpenJLPT numbers them 5 to 2.
EASIEST_LEVEL, HARDEST_TARGET_LEVEL = 5, 2
# 12 random bytes: 16 URL-safe characters, never guessable from the internal ID.
PUBLIC_ID_BYTES = 12
QUIZ_EVENT = {"meaning": QUIZ_MEANING, "reading": QUIZ_READING}


class LearnerNotFoundError(LookupError):
    """No learner has this ID."""


class UnknownWordError(LookupError):
    """The word ID isn't in the dictionary (OpenJLPT or the supplement)."""


def check_target_level(target_level: int) -> None:
    if not HARDEST_TARGET_LEVEL <= target_level <= EASIEST_LEVEL:
        raise ValueError(f"target level {target_level} is outside N5 to N2: use 5 (N5) to 2 (N2)")


def check_timezone(timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown timezone {timezone!r}: use an IANA name such as Asia/Jakarta") from None


LEARNER_FIELDS = ("id", "public_id", "cohort_id", "target_level", "timezone", "exam_date")
LEARNER_COLUMNS = ", ".join(LEARNER_FIELDS)


def _learner(row: Row[Any]) -> Learner:
    return Learner.model_validate(dict(zip(LEARNER_FIELDS, row, strict=True)))


async def _select_learner(connection: AsyncConnection, learner_id: int, *, lock: bool) -> Learner:
    lock_clause = " FOR UPDATE" if lock else ""
    row = (
        await connection.execute(
            text(f"SELECT {LEARNER_COLUMNS} FROM learning.learners WHERE id = :id{lock_clause}"),  # noqa: S608
            {"id": learner_id},
        )
    ).first()
    if row is None:
        raise LearnerNotFoundError(f"no learner with ID {learner_id}")
    return _learner(row)


async def load_learner(connection: AsyncConnection, learner_id: int) -> Learner:
    return await _select_learner(connection, learner_id, lock=False)


async def lock_learner(connection: AsyncConnection, learner_id: int) -> Learner:
    """The learner, with their row locked until the transaction ends: one writer per learner at a time."""
    return await _select_learner(connection, learner_id, lock=True)


async def find_learner(connection: AsyncConnection, public_id: str) -> Learner:
    row = (
        await connection.execute(
            text(f"SELECT {LEARNER_COLUMNS} FROM learning.learners WHERE public_id = :public_id"),  # noqa: S608
            {"public_id": public_id},
        )
    ).first()
    if row is None:
        raise LearnerNotFoundError(f"no learner with public ID {public_id!r}")
    return _learner(row)


async def create_learner(
    connection: AsyncConnection,
    *,
    nickname: str,
    target_level: int,
    timezone: str,
    exam_date: date | None,
    cohort_id: int,
    public_id: str | None,
) -> Learner:
    check_target_level(target_level)
    check_timezone(timezone)
    row = (
        await connection.execute(
            text(
                "INSERT INTO learning.learners (public_id, cohort_id, nickname, target_level, exam_date, timezone) "
                "VALUES (:public_id, :cohort_id, :nickname, :target_level, :exam_date, :timezone) "
                "RETURNING id, public_id, cohort_id, target_level, timezone, exam_date"
            ),
            {
                "public_id": public_id or secrets.token_urlsafe(PUBLIC_ID_BYTES),
                "cohort_id": cohort_id,
                "nickname": nickname,
                "target_level": target_level,
                "exam_date": exam_date,
                "timezone": timezone,
            },
        )
    ).one()
    learner = _learner(row)
    # No events yet, so the rebuild gives five empty coverage rows and the starting candidates.
    await rebuild_learners(connection, [learner.id])
    return learner


async def update_learner(
    connection: AsyncConnection, learner_id: int, *, target_level: int | None = None, timezone: str | None = None
) -> None:
    """A new level changes the candidates; a new timezone changes which day each answer fell on. Both rebuild."""
    await lock_learner(connection, learner_id)
    if target_level is not None:
        check_target_level(target_level)
        await connection.execute(
            text("UPDATE learning.learners SET target_level = :level WHERE id = :id"),
            {"level": target_level, "id": learner_id},
        )
    if timezone is not None:
        check_timezone(timezone)
        await connection.execute(
            text("UPDATE learning.learners SET timezone = :zone WHERE id = :id"), {"zone": timezone, "id": learner_id}
        )
    await rebuild_learners(connection, [learner_id])


async def check_word(dictionary: AsyncEngine, word_id: str) -> None:
    async with dictionary.connect() as connection:
        exists = await connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM ojlpt.vocab WHERE id = :id "
                "UNION SELECT 1 FROM ojlpt.supplement_word WHERE id = :id)"
            ),
            {"id": word_id},
        )
    if not exists:
        raise UnknownWordError(f"{word_id!r} isn't a word in the dictionary")


async def _append_event(
    connection: AsyncConnection, learner: Learner, event_type: int, item_id: str, result: int | None, at: datetime
) -> None:
    await connection.execute(
        text(
            "INSERT INTO learning.learning_events (learner_id, cohort_id, event_type, item_id, result, occurred_at) "
            "VALUES (:learner, :cohort, :type, :item, :result, :at)"
        ),
        {
            "learner": learner.id,
            "cohort": learner.cohort_id,
            "type": event_type,
            "item": item_id,
            "result": result,
            "at": at,
        },
    )
    await connection.execute(
        text("UPDATE learning.learners SET last_active_at = greatest(last_active_at, :at) WHERE id = :id"),
        {"at": at, "id": learner.id},
    )


async def _read_state(connection: AsyncConnection, learner_id: int, word_id: str) -> ItemState:
    row = (
        await connection.execute(
            text(
                "SELECT is_known, correct_days, last_correct_day, correct_count, wrong_count, box, due_at, "
                "last_seen_at FROM learning.learner_state WHERE learner_id = :learner AND item_id = :item"
            ),
            {"learner": learner_id, "item": word_id},
        )
    ).first()
    if row is None:
        return ItemState()
    return ItemState(*tuple(row))


async def _write_state(connection: AsyncConnection, learner_id: int, word_id: str, state: ItemState) -> None:
    await connection.execute(
        text(
            "INSERT INTO learning.learner_state (learner_id, item_id, is_known, correct_days, last_correct_day, "
            "correct_count, wrong_count, box, due_at, last_seen_at) "
            "VALUES (:learner, :item, :is_known, :correct_days, :last_correct_day, :correct_count, :wrong_count, "
            ":box, :due_at, :last_seen_at) "
            "ON CONFLICT (learner_id, item_id) DO UPDATE SET is_known = excluded.is_known, "
            "correct_days = excluded.correct_days, last_correct_day = excluded.last_correct_day, "
            "correct_count = excluded.correct_count, wrong_count = excluded.wrong_count, box = excluded.box, "
            "due_at = excluded.due_at, last_seen_at = excluded.last_seen_at"
        ),
        {
            "learner": learner_id,
            "item": word_id,
            "is_known": state.is_known,
            "correct_days": state.correct_days,
            "last_correct_day": state.last_correct_day,
            "correct_count": state.correct_count,
            "wrong_count": state.wrong_count,
            "box": state.box,
            "due_at": state.due_at,
            "last_seen_at": state.last_seen_at,
        },
    )


async def _kanji_of(connection: AsyncConnection, word_id: str) -> list[str]:
    found = await connection.scalars(
        text("SELECT kanji FROM learning.dictionary_word_kanji WHERE word_id = :id ORDER BY kanji"), {"id": word_id}
    )
    return [str(kanji) for kanji in found]


async def _change_kanji(connection: AsyncConnection, learner_id: int, kanji: str, delta: int) -> None:
    """Count one more (or one fewer) known word with this kanji; a count crossing zero changes coverage."""
    before = await connection.scalar(
        text("SELECT known_words FROM learning.learner_kanji WHERE learner_id = :learner AND kanji = :kanji"),
        {"learner": learner_id, "kanji": kanji},
    )
    count_before = int(before or 0)
    count_after = count_before + delta
    if count_after == 0:
        await connection.execute(
            text("DELETE FROM learning.learner_kanji WHERE learner_id = :learner AND kanji = :kanji"),
            {"learner": learner_id, "kanji": kanji},
        )
    else:
        await connection.execute(
            text(
                "INSERT INTO learning.learner_kanji (learner_id, kanji, known_words) VALUES (:learner, :kanji, :count) "
                "ON CONFLICT (learner_id, kanji) DO UPDATE SET known_words = excluded.known_words"
            ),
            {"learner": learner_id, "kanji": kanji, "count": count_after},
        )
    if (count_before == 0) != (count_after == 0):
        await connection.execute(
            text(
                "UPDATE learning.learner_coverage SET kanji_known = kanji_known + :delta WHERE learner_id = :learner "
                "AND level = (SELECT level FROM learning.dictionary_kanji WHERE kanji = :kanji)"
            ),
            {"delta": delta, "learner": learner_id, "kanji": kanji},
        )


async def _refresh_candidates(connection: AsyncConnection, learner_id: int, word_id: str, kanji: list[str]) -> None:
    """Recompute the candidates for the word and every word sharing a kanji with it: only their status can change."""
    affected = [word_id] + [
        str(other)
        for other in await connection.scalars(
            text("SELECT DISTINCT word_id FROM learning.dictionary_word_kanji WHERE kanji = ANY(:kanji)"),
            {"kanji": kanji},
        )
    ]
    parameters = {"learner_ids": [learner_id], "word_ids": affected}
    await connection.execute(
        text("DELETE FROM learning.learner_candidate WHERE learner_id = :learner AND word_id = ANY(:word_ids)"),
        {"learner": learner_id, "word_ids": affected},
    )
    await connection.execute(
        text(
            "INSERT INTO learning.learner_candidate (learner_id, word_id, level, new_kanji, leverage, commonness) "
            + candidate_query("learning.learner_state", only_words=True)
        ),
        parameters,
    )


async def _known_changed(connection: AsyncConnection, learner_id: int, word_id: str, is_known: bool) -> None:
    delta = 1 if is_known else -1
    kanji = await _kanji_of(connection, word_id)
    for each in kanji:
        await _change_kanji(connection, learner_id, each, delta)
    await connection.execute(
        text(
            "UPDATE learning.learner_coverage SET words_known = words_known + :delta WHERE learner_id = :learner "
            "AND level = (SELECT level FROM learning.dictionary_words WHERE word_id = :word)"
        ),
        {"delta": delta, "learner": learner_id, "word": word_id},
    )
    await _refresh_candidates(connection, learner_id, word_id, kanji)


async def _count_activity(
    connection: AsyncConnection, learner: Learner, at: datetime, column: str, *, correct: bool
) -> None:
    day = at.astimezone(ZoneInfo(learner.timezone)).date()
    is_quiz = column == "quiz_answers"
    await connection.execute(
        text(
            "INSERT INTO learning.learner_daily_activity (learner_id, day, quiz_answers, quiz_correct, words_marked, "
            "sentences_read) VALUES (:learner, :day, :quiz, :correct, :marked, :read) "
            "ON CONFLICT (learner_id, day) DO UPDATE SET "
            "quiz_answers = learner_daily_activity.quiz_answers + excluded.quiz_answers, "
            "quiz_correct = learner_daily_activity.quiz_correct + excluded.quiz_correct, "
            "words_marked = learner_daily_activity.words_marked + excluded.words_marked, "
            "sentences_read = learner_daily_activity.sentences_read + excluded.sentences_read"
        ),
        {
            "learner": learner.id,
            "day": day,
            "quiz": 1 if is_quiz else 0,
            "correct": 1 if is_quiz and correct else 0,
            "marked": 1 if column == "words_marked" else 0,
            "read": 1 if column == "sentences_read" else 0,
        },
    )


async def apply_word_event(
    connection: AsyncConnection,
    learner_id: int,
    word_id: str,
    event_type: int,
    at: datetime,
    *,
    is_correct: bool = False,
) -> None:
    """Append one word event and bring every summary up to date with it."""
    learner = await lock_learner(connection, learner_id)
    is_quiz = event_type in (QUIZ_MEANING, QUIZ_READING)
    await _append_event(connection, learner, event_type, word_id, (1 if is_correct else 0) if is_quiz else None, at)
    before = await _read_state(connection, learner.id, word_id)
    if event_type == MARKED_KNOWN:
        after = after_marked_known(before, at=at)
    elif event_type == UNMARKED_KNOWN:
        after = after_unmarked_known(before, at=at)
    else:
        local_day = at.astimezone(ZoneInfo(learner.timezone)).date()
        after = after_quiz_answer(before, is_correct=is_correct, at=at, local_day=local_day)
    await _write_state(connection, learner.id, word_id, after)
    if after.is_known != before.is_known:
        await _known_changed(connection, learner.id, word_id, after.is_known)
    if is_quiz:
        await _count_activity(connection, learner, at, "quiz_answers", correct=is_correct)
    elif event_type == MARKED_KNOWN:
        await _count_activity(connection, learner, at, "words_marked", correct=False)


async def apply_sentence_read(connection: AsyncConnection, learner_id: int, sentence_id: int, at: datetime) -> None:
    learner = await lock_learner(connection, learner_id)
    await _append_event(connection, learner, SENTENCE_READ, str(sentence_id), None, at)
    await _count_activity(connection, learner, at, "sentences_read", correct=False)
