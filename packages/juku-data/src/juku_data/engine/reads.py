"""The engine's read side: what the $0 pages and the agents' tools show (LE1, LE3-LE6).

Every query here reads the summaries, never `learning_events` (fitness
function FF2). Where a page needs words' spellings or meanings, a second
query fetches them from the dict database by ID: Postgres can't join
across databases (ADR-006).
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from fractions import Fraction
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_data.engine.models import (
    DayActivity,
    Learner,
    LevelCoverage,
    MistakeItem,
    Mistakes,
    Plan,
    Progress,
    ReadingSentence,
    ReadingSentences,
    RecentActivity,
    Recommendations,
    RecommendedWord,
    level_name,
)

RECOMMENDATIONS = 10
# ADR-010: at most this many of the ten suggestions share one new kanji.
MAX_PER_NEW_KANJI = 3
READING_SENTENCES = 10
# LE5: the share of the target level (and everything easier) the plan aims
# for by the exam. A fraction, so 80% of 674 words is exactly 539.2.
TARGET_COVERAGE = Fraction(4, 5)
DAYS_PER_WEEK = 7

# Susumu (ADR-010): lexicographic, with no tuned weights. Gaps from easier
# levels first, then the new kanji's leverage, then commonness, then the
# stable ID; then the variety cap.
RANKED_CANDIDATES = f"""
WITH ranked AS (
    SELECT c.word_id, c.level, c.new_kanji, c.leverage,
           row_number() OVER (ORDER BY (c.level > :target_level) DESC, c.leverage DESC, c.commonness, c.word_id)
               AS rank
    FROM learning.learner_candidate c
    WHERE c.learner_id = :learner_id
),
varied AS (
    SELECT r.*, row_number() OVER (PARTITION BY r.new_kanji ORDER BY r.rank) AS nth_with_this_kanji
    FROM ranked r
)
SELECT word_id, level, new_kanji, leverage FROM varied
WHERE new_kanji IS NULL OR nth_with_this_kanji <= {MAX_PER_NEW_KANJI}
ORDER BY rank
LIMIT :limit
"""  # noqa: S608 (a constant)

# LE4, from spike 2's query: sentences whose content words are all known
# but one, shortest first. A sentence with one content word, unknown,
# counts too.
READING = """
WITH hits AS (
    SELECT sw.sentence_id, count(*) AS known_count
    FROM ojlpt.sentence_word sw WHERE sw.word_id = ANY(:known) GROUP BY sw.sentence_id
),
one_unknown AS (
    SELECT s.sentence_id FROM ojlpt.sentence s JOIN hits h USING (sentence_id)
    WHERE s.content_words - h.known_count = 1
    UNION ALL
    SELECT s.sentence_id FROM ojlpt.sentence s
    WHERE s.content_words = 1 AND NOT EXISTS (SELECT 1 FROM hits h WHERE h.sentence_id = s.sentence_id)
),
found AS (
    SELECT s.sentence_id, s.ja, s.furigana, s.en, s.tatoeba_id,
           (SELECT sw.word_id FROM ojlpt.sentence_word sw
            WHERE sw.sentence_id = s.sentence_id AND sw.word_id <> ALL(:known) LIMIT 1) AS new_word_id
    FROM one_unknown o JOIN ojlpt.sentence s USING (sentence_id)
    ORDER BY length(s.ja), s.sentence_id
    LIMIT :limit
)
SELECT f.*, coalesce(v.word, sup.word) AS new_word
FROM found f
LEFT JOIN ojlpt.vocab v ON v.id = f.new_word_id
LEFT JOIN ojlpt.supplement_word sup ON sup.id = f.new_word_id
ORDER BY length(f.ja), f.sentence_id
"""

WORD_DETAILS = """
SELECT id, word, reading, meanings FROM ojlpt.vocab WHERE id = ANY(:ids)
UNION ALL
SELECT id, word, reading, to_jsonb(string_to_array(meanings, '; ')) FROM ojlpt.supplement_word WHERE id = ANY(:ids)
"""


async def _target_level(connection: AsyncConnection, learner_id: int) -> int:
    return int(
        await connection.scalar(text("SELECT target_level FROM learning.learners WHERE id = :id"), {"id": learner_id})
    )


async def word_details(dictionary: AsyncEngine, word_ids: list[str]) -> dict[str, tuple[str, str, list[str]]]:
    """Spelling, reading and English meanings by ID, from the dict database."""
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(WORD_DETAILS), {"ids": word_ids})).all()
    details: dict[str, tuple[str, str, list[str]]] = {}
    for word_id, word, reading, meanings in rows:
        parsed: Any = json.loads(meanings) if isinstance(meanings, str) else meanings
        details[str(word_id)] = (str(word), str(reading), [str(meaning) for meaning in parsed])
    return details


async def known_word_ids(app: AsyncEngine, learner_id: int) -> list[str]:
    async with app.connect() as connection:
        found = await connection.scalars(
            text("SELECT item_id FROM learning.learner_state WHERE learner_id = :id AND is_known ORDER BY item_id"),
            {"id": learner_id},
        )
        return [str(word_id) for word_id in found]


async def get_progress(app: AsyncEngine, learner_id: int) -> Progress:
    async with app.connect() as connection:
        target_level = await _target_level(connection, learner_id)
        rows = (
            await connection.execute(
                text(
                    "SELECT c.level, c.words_known, c.kanji_known, "
                    "(SELECT count(*) FROM learning.dictionary_words w WHERE w.level = c.level) AS words_total, "
                    "(SELECT count(*) FROM learning.dictionary_kanji k WHERE k.level = c.level) AS kanji_total "
                    "FROM learning.learner_coverage c WHERE c.learner_id = :id ORDER BY c.level DESC"
                ),
                {"id": learner_id},
            )
        ).all()
        known_words = await connection.scalar(
            text("SELECT count(*) FROM learning.learner_state WHERE learner_id = :id AND is_known"), {"id": learner_id}
        )
    levels = [
        LevelCoverage(
            level=level,
            level_name=level_name(level),
            words_known=words_known,
            words_total=words_total,
            kanji_known=kanji_known,
            kanji_total=kanji_total,
            word_coverage=words_known / words_total if words_total else 0.0,
            kanji_coverage=kanji_known / kanji_total if kanji_total else 0.0,
        )
        for level, words_known, kanji_known, words_total, kanji_total in rows
    ]
    return Progress(target_level=target_level, known_words=int(known_words or 0), levels=levels)


def recommendation_reason(level: int, target_level: int, new_kanji: str | None, leverage: int) -> str:
    """ADR-010's reason, built from the row: e.g. "1 kanji baru: 日, muncul di 34 kata N5."."""
    gap = f"Kata {level_name(level)} yang belum dikuasai. " if level > target_level else ""
    if new_kanji is None:
        return gap + "Tanpa kanji baru."
    return gap + f"1 kanji baru: {new_kanji}, muncul di {leverage} kata {level_name(target_level)}."


async def ranked_candidates(
    app: AsyncEngine, learner_id: int, limit: int
) -> tuple[int, list[tuple[str, int, str | None, int]]]:
    """The learner's target level, and their best candidates in Susumu's order."""
    async with app.connect() as connection:
        target_level = await _target_level(connection, learner_id)
        rows = (
            await connection.execute(
                text(RANKED_CANDIDATES), {"learner_id": learner_id, "target_level": target_level, "limit": limit}
            )
        ).all()
    return target_level, [(str(row[0]), int(row[1]), row[2], int(row[3])) for row in rows]


async def recommend_words(app: AsyncEngine, dictionary: AsyncEngine, learner_id: int) -> Recommendations:
    target_level, ranked = await ranked_candidates(app, learner_id, RECOMMENDATIONS)
    details = await word_details(dictionary, [word_id for word_id, *_ in ranked])
    words = [
        RecommendedWord(
            word_id=word_id,
            word=details[word_id][0],
            reading=details[word_id][1],
            level=level,
            meanings=details[word_id][2],
            new_kanji=new_kanji,
            leverage=leverage,
            reason=recommendation_reason(level, target_level, new_kanji, leverage),
        )
        for word_id, level, new_kanji, leverage in ranked
    ]
    return Recommendations(words=words)


async def get_mistakes(app: AsyncEngine, dictionary: AsyncEngine, learner_id: int, now: datetime) -> Mistakes:
    async with app.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT item_id, box, due_at FROM learning.learner_state "
                    "WHERE learner_id = :id AND box IS NOT NULL ORDER BY due_at, item_id"
                ),
                {"id": learner_id},
            )
        ).all()
    details = await word_details(dictionary, [str(row[0]) for row in rows])
    items = [
        MistakeItem(
            word_id=str(word_id),
            word=details[str(word_id)][0],
            reading=details[str(word_id)][1],
            box=int(box),
            due_at=due_at,
            is_due=due_at <= now,
        )
        for word_id, box, due_at in rows
    ]
    return Mistakes(items=items)


async def find_reading_sentences(app: AsyncEngine, dictionary: AsyncEngine, learner_id: int) -> ReadingSentences:
    known = await known_word_ids(app, learner_id)
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(READING), {"known": known, "limit": READING_SENTENCES})).all()
    sentences = [
        ReadingSentence(
            sentence_id=row.sentence_id,
            ja=row.ja,
            furigana=row.furigana,
            en=row.en,
            tatoeba_id=row.tatoeba_id,
            new_word_id=row.new_word_id,
            new_word=row.new_word,
        )
        for row in rows
    ]
    return ReadingSentences(sentences=sentences)


def weeks_until(exam_date: date | None, today: date) -> int | None:
    """Whole weeks left, rounding a part week up; None with no exam date or once it has passed."""
    if exam_date is None or exam_date < today:
        return None
    return max(1, math.ceil((exam_date - today).days / DAYS_PER_WEEK))


async def get_plan(app: AsyncEngine, learner: Learner, today: date) -> Plan:
    """LE5: words a week = ceil((80% of the words at the target level and easier - those known) / weeks left)."""
    progress = await get_progress(app, learner.id)
    in_scope = [level for level in progress.levels if level.level >= learner.target_level]
    words_in_scope = sum(level.words_total for level in in_scope)
    words_known = sum(level.words_known for level in in_scope)
    words_needed = max(0, math.ceil(TARGET_COVERAGE * words_in_scope) - words_known)
    weeks_left = weeks_until(learner.exam_date, today)
    words_per_week = math.ceil(words_needed / weeks_left) if weeks_left else None
    percent = int(TARGET_COVERAGE * 100)
    formula = (
        f"kata per minggu = ({percent}% x {words_in_scope} kata {level_name(learner.target_level)} dan di bawahnya "
        f"- {words_known} yang sudah dikuasai) / {weeks_left} minggu, dibulatkan ke atas"
        if weeks_left
        else f"target: {percent}% dari {words_in_scope} kata; isi tanggal ujian untuk melihat kecepatan per minggu"
    )
    return Plan(
        target_level=learner.target_level,
        target_coverage=float(TARGET_COVERAGE),
        words_in_scope=words_in_scope,
        words_known=words_known,
        words_needed=words_needed,
        exam_date=learner.exam_date,
        weeks_left=weeks_left,
        words_per_week=words_per_week,
        formula=formula,
    )


async def get_recent_activity(app: AsyncEngine, learner_id: int, today: date, days: int) -> RecentActivity:
    async with app.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT day, quiz_answers, quiz_correct, words_marked, sentences_read "
                    "FROM learning.learner_daily_activity "
                    "WHERE learner_id = :id AND day > :first_excluded AND day <= :today ORDER BY day"
                ),
                {"id": learner_id, "first_excluded": today - timedelta(days=days), "today": today},
            )
        ).all()
    return RecentActivity(
        days=[
            DayActivity(day=day, quiz_answers=answers, quiz_correct=correct, words_marked=marked, sentences_read=read)
            for day, answers, correct, marked, read in rows
        ]
    )
