"""Learner summaries recomputed from the event history, in SQL (scale path; fitness function FF3).

The incremental path (engine/writes.py) updates the summaries event by
event, with the rules in engine/state.py. This module derives the same
summaries from the events alone, set-based, for three jobs:
- `verify_state`: compare the two, nightly in production and on every
  commit for the fixtures (FF3);
- `rebuild_learners`: replace a learner's summaries, after their level or
  timezone changes, or to build the synthetic database;
- the candidate query, which the incremental path also runs for just the
  words an event affects.

Only these functions read `learning_events`; the read paths never do (FF2).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from juku_data.engine.state import CORRECT_DAYS_TO_KNOW, LAST_BOX, LEITNER_INTERVAL_DAYS

# Event types (learning.event_types).
MARKED_KNOWN, UNMARKED_KNOWN, QUIZ_MEANING, QUIZ_READING, SENTENCE_READ = 1, 2, 3, 4, 5
WORD_EVENTS = (MARKED_KNOWN, UNMARKED_KNOWN, QUIZ_MEANING, QUIZ_READING)
INTERVALS_ARRAY = "ARRAY[" + ", ".join(str(LEITNER_INTERVAL_DAYS[box]) for box in sorted(LEITNER_INTERVAL_DAYS)) + "]"

# One row per (learner, word) the learner has done anything with: LE1's
# known rule counted since the last unmark, and LE6's box (1 + the right
# answers since the last wrong one, at most 5).
EXPECTED_STATE = f"""
WITH ev AS (
    SELECT e.learner_id, e.item_id, e.event_type, e.result, e.occurred_at,
           (e.occurred_at AT TIME ZONE l.timezone)::date AS local_day
    FROM learning.learning_events e
    JOIN learning.learners l ON l.id = e.learner_id
    WHERE e.learner_id = ANY(:learner_ids) AND e.event_type IN ({", ".join(map(str, WORD_EVENTS))})
),
last_unmark AS (
    SELECT learner_id, item_id, max(occurred_at) AS unmarked_at
    FROM ev WHERE event_type = {UNMARKED_KNOWN} GROUP BY learner_id, item_id
),
since_unmark AS (
    SELECT ev.* FROM ev LEFT JOIN last_unmark u USING (learner_id, item_id)
    WHERE u.unmarked_at IS NULL OR ev.occurred_at > u.unmarked_at
),
knowing AS (
    SELECT learner_id, item_id,
           bool_or(event_type = {MARKED_KNOWN}) AS is_marked,
           count(DISTINCT local_day) FILTER (WHERE event_type IN ({QUIZ_MEANING}, {QUIZ_READING}) AND result = 1)
               AS correct_days,
           max(local_day) FILTER (WHERE event_type IN ({QUIZ_MEANING}, {QUIZ_READING}) AND result = 1)
               AS last_correct_day
    FROM since_unmark GROUP BY learner_id, item_id
),
answers AS (
    SELECT learner_id, item_id,
           count(*) FILTER (WHERE result = 1) AS correct_count,
           count(*) FILTER (WHERE result = 0) AS wrong_count,
           max(occurred_at) FILTER (WHERE result = 0) AS last_wrong_at,
           max(occurred_at) AS last_answer_at
    FROM ev WHERE event_type IN ({QUIZ_MEANING}, {QUIZ_READING}) GROUP BY learner_id, item_id
),
boxes AS (
    SELECT a.*,
           CASE WHEN a.last_wrong_at IS NULL THEN NULL
                ELSE least(1 + (SELECT count(*) FROM ev r
                                WHERE r.learner_id = a.learner_id AND r.item_id = a.item_id
                                  AND r.event_type IN ({QUIZ_MEANING}, {QUIZ_READING}) AND r.result = 1
                                  AND r.occurred_at > a.last_wrong_at), {LAST_BOX})
           END AS box
    FROM answers a
),
seen AS (SELECT learner_id, item_id, max(occurred_at) AS last_seen_at FROM ev GROUP BY learner_id, item_id)
SELECT s.learner_id, s.item_id,
       coalesce(k.is_marked OR k.correct_days >= {CORRECT_DAYS_TO_KNOW}, false) AS is_known,
       coalesce(k.correct_days, 0)::smallint AS correct_days,
       k.last_correct_day,
       coalesce(b.correct_count, 0)::integer AS correct_count,
       coalesce(b.wrong_count, 0)::integer AS wrong_count,
       b.box::smallint AS box,
       b.last_answer_at + make_interval(days => ({INTERVALS_ARRAY})[b.box]) AS due_at,
       s.last_seen_at
FROM seen s
LEFT JOIN knowing k USING (learner_id, item_id)
LEFT JOIN boxes b USING (learner_id, item_id)
"""  # noqa: S608 (built from this module's constants only)

EXPECTED_ACTIVITY = f"""
SELECT e.learner_id, (e.occurred_at AT TIME ZONE l.timezone)::date AS day,
       count(*) FILTER (WHERE e.event_type IN ({QUIZ_MEANING}, {QUIZ_READING}))::integer AS quiz_answers,
       count(*) FILTER (WHERE e.event_type IN ({QUIZ_MEANING}, {QUIZ_READING}) AND e.result = 1)::integer
           AS quiz_correct,
       count(*) FILTER (WHERE e.event_type = {MARKED_KNOWN})::integer AS words_marked,
       count(*) FILTER (WHERE e.event_type = {SENTENCE_READ})::integer AS sentences_read
FROM learning.learning_events e
JOIN learning.learners l ON l.id = e.learner_id
-- Unmarking a word isn't counted as activity, so a day with only that has no row.
WHERE e.learner_id = ANY(:learner_ids) AND e.event_type <> {UNMARKED_KNOWN}
GROUP BY e.learner_id, day
"""  # noqa: S608


def kanji_query(state_table: str) -> str:
    """Each learner's known kanji: the kanji in their known words, with how many known words contain each."""
    return f"""
    SELECT s.learner_id, wk.kanji, count(*)::integer AS known_words
    FROM {state_table} s
    JOIN learning.dictionary_word_kanji wk ON wk.word_id = s.item_id
    WHERE s.is_known AND s.learner_id = ANY(:learner_ids)
    GROUP BY s.learner_id, wk.kanji
    """  # noqa: S608 (the table name is one of this package's own)


def coverage_query(state_table: str, kanji_table: str) -> str:
    """LE1's coverage: known words and kanji per level, for all five levels."""
    return f"""
    SELECT l.id AS learner_id, levels.level::smallint AS level,
           (SELECT count(*) FROM {state_table} s JOIN learning.dictionary_words w ON w.word_id = s.item_id
            WHERE s.learner_id = l.id AND s.is_known AND w.level = levels.level)::integer AS words_known,
           (SELECT count(*) FROM {kanji_table} lk JOIN learning.dictionary_kanji k ON k.kanji = lk.kanji
            WHERE lk.learner_id = l.id AND k.level = levels.level)::integer AS kanji_known
    FROM learning.learners l CROSS JOIN generate_series(1, 5) AS levels(level)
    WHERE l.id = ANY(:learner_ids)
    """  # noqa: S608


def candidate_query(state_table: str, *, only_words: bool = False) -> str:
    """ADR-010's candidates: at the learner's level or easier, not known, at most one unknown kanji.

    Known kanji are every kanji of the easier levels plus those in known
    words. With `only_words`, only the words in `:word_ids` are computed:
    the incremental path's update after one word changes.
    """
    word_filter = "AND w.word_id = ANY(:word_ids)" if only_words else ""
    return f"""
    WITH target AS (
        SELECT id AS learner_id, target_level FROM learning.learners WHERE id = ANY(:learner_ids)
    ),
    known_words AS (
        SELECT s.learner_id, s.item_id AS word_id FROM {state_table} s
        WHERE s.is_known AND s.learner_id = ANY(:learner_ids)
    ),
    known_kanji AS (
        SELECT t.learner_id, k.kanji FROM target t JOIN learning.dictionary_kanji k ON k.level > t.target_level
        UNION
        SELECT kw.learner_id, wk.kanji FROM known_words kw JOIN learning.dictionary_word_kanji wk USING (word_id)
    ),
    candidate AS (
        SELECT t.learner_id, t.target_level, w.word_id, w.level, w.commonness,
               count(wk.kanji) FILTER (WHERE kk.kanji IS NULL) AS unknown_kanji,
               min(wk.kanji) FILTER (WHERE kk.kanji IS NULL) AS new_kanji
        FROM target t
        JOIN learning.dictionary_words w ON w.level >= t.target_level
        LEFT JOIN learning.dictionary_word_kanji wk ON wk.word_id = w.word_id
        LEFT JOIN known_kanji kk ON kk.learner_id = t.learner_id AND kk.kanji = wk.kanji
        WHERE NOT EXISTS (SELECT 1 FROM known_words kw WHERE kw.learner_id = t.learner_id AND kw.word_id = w.word_id)
          {word_filter}
        GROUP BY t.learner_id, t.target_level, w.word_id, w.level, w.commonness
    )
    SELECT c.learner_id, c.word_id, c.level, c.new_kanji, coalesce(kl.words, 0) AS leverage, c.commonness
    FROM candidate c
    LEFT JOIN learning.kanji_leverage kl ON kl.kanji = c.new_kanji AND kl.level = c.target_level
    WHERE c.unknown_kanji <= 1
    """  # noqa: S608


@dataclass(frozen=True)
class Summary:
    """One summary table: its name, the columns compared, and the query giving its expected rows."""

    table: str
    columns: str
    expected_sql: str


EXPECTED_TABLE = {
    "learner_state": "expected_state",
    "learner_kanji": "expected_kanji",
    "learner_coverage": "expected_coverage",
    "learner_candidate": "expected_candidate",
    "learner_daily_activity": "expected_activity",
}
SUMMARIES = [
    Summary(
        "learner_state",
        "learner_id, item_id, is_known, correct_days, last_correct_day, correct_count, wrong_count, box, due_at, "
        "last_seen_at",
        EXPECTED_STATE,
    ),
    Summary("learner_kanji", "learner_id, kanji, known_words", kanji_query("pg_temp.expected_state")),
    Summary(
        "learner_coverage",
        "learner_id, level, words_known, kanji_known",
        coverage_query("pg_temp.expected_state", "pg_temp.expected_kanji"),
    ),
    Summary(
        "learner_candidate",
        "learner_id, word_id, level, new_kanji, leverage, commonness",
        candidate_query("pg_temp.expected_state"),
    ),
    Summary(
        "learner_daily_activity",
        "learner_id, day, quiz_answers, quiz_correct, words_marked, sentences_read",
        EXPECTED_ACTIVITY,
    ),
]
ALL_LEARNERS = "SELECT id FROM learning.learners ORDER BY id"
DIFFERENCES_SHOWN = 3


async def _learner_ids(connection: AsyncConnection, learner_ids: Sequence[int] | None) -> list[int]:
    if learner_ids is not None:
        return list(learner_ids)
    return [int(learner_id) for learner_id in await connection.scalars(text(ALL_LEARNERS))]


async def _compute_expected(connection: AsyncConnection, learner_ids: list[int]) -> None:
    """Temporary tables holding every summary as the events say it should be (dropped at commit)."""
    for summary in SUMMARIES:
        name = EXPECTED_TABLE[summary.table]
        await connection.execute(text(f"DROP TABLE IF EXISTS pg_temp.{name}"))
        await connection.execute(
            text(f"CREATE TEMPORARY TABLE {name} ON COMMIT DROP AS {summary.expected_sql}"),
            {"learner_ids": learner_ids},
        )


async def rebuild_learners(connection: AsyncConnection, learner_ids: Sequence[int] | None = None) -> None:
    """Replace the learners' summaries with a recompute from their events. Run inside the caller's transaction."""
    ids = await _learner_ids(connection, learner_ids)
    await _compute_expected(connection, ids)
    for summary in SUMMARIES:
        await connection.execute(
            text(f"DELETE FROM learning.{summary.table} WHERE learner_id = ANY(:learner_ids)"),  # noqa: S608
            {"learner_ids": ids},
        )
        await connection.execute(
            text(
                f"INSERT INTO learning.{summary.table} ({summary.columns}) "  # noqa: S608 (names from SUMMARIES)
                f"SELECT {summary.columns} FROM pg_temp.{EXPECTED_TABLE[summary.table]}"
            )
        )


async def _differences(connection: AsyncConnection, summary: Summary, learner_ids: list[int]) -> list[str]:
    expected = f"pg_temp.{EXPECTED_TABLE[summary.table]}"
    actual = f"(SELECT {summary.columns} FROM learning.{summary.table} WHERE learner_id = ANY(:learner_ids)) actual"  # noqa: S608
    found: list[str] = []
    for label, left, right in (("unexpected", actual, expected), ("missing", expected, actual)):
        rows = (
            await connection.execute(
                text(f"SELECT {summary.columns} FROM {left} EXCEPT SELECT {summary.columns} FROM {right} LIMIT 50"),  # noqa: S608
                {"learner_ids": learner_ids},
            )
        ).all()
        for row in rows[:DIFFERENCES_SHOWN]:
            found.append(f"{summary.table}: {label} row {tuple(row)}")
        if len(rows) > DIFFERENCES_SHOWN:
            found.append(f"{summary.table}: and {len(rows) - DIFFERENCES_SHOWN} more {label} rows")
    return found


async def verify_learners(connection: AsyncConnection, learner_ids: Sequence[int] | None = None) -> list[str]:
    """Every difference between the summaries and a recompute; an empty list means FF3 holds."""
    ids = await _learner_ids(connection, learner_ids)
    await _compute_expected(connection, ids)
    differences: list[str] = []
    for summary in SUMMARIES:
        differences += await _differences(connection, summary, ids)
    return differences
