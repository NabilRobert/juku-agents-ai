"""A synthetic database of 5,000 learners, for fitness function FF1 (scale path).

Real-shaped data at the size the design claims to handle, made in SQL in
a few statements, with no randomness, so every build is the same:
- learners spread over the levels (40% N5, 30% N4, 20% N3, 10% N2), four
  timezones and three cohorts;
- each knows 50 to 800 words, marked known in a fixed order (easier
  levels first, then commonness), and has answered 100 quiz questions on
  the next 60 words, about 70% right;
- one more learner, `syn-heavy`, at N2, knows 4,000 words: the case
  spike 2 found slowest;
- the summaries are then built by the engine's own recompute, in batches.

About 2.6 million events. It's for measuring plans and timings only:
never real data, and never in production.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.engine.recompute import MARKED_KNOWN, QUIZ_MEANING, rebuild_learners

SYNTHETIC_LEARNERS = 5000
HEAVY_LEARNER_PUBLIC_ID = "syn-heavy"
HEAVY_LEARNER_KNOWN_WORDS = 4000
QUIZ_ANSWERS_PER_LEARNER = 100
WORDS_IN_PROGRESS = 60
REBUILD_BATCH = 250

CREATE_LEARNERS = """
INSERT INTO learning.learners (public_id, cohort_id, nickname, target_level, timezone)
SELECT 'syn-' || g, 1 + g % 3, 'synthetic',
       CASE WHEN g % 10 < 4 THEN 5 WHEN g % 10 < 7 THEN 4 WHEN g % 10 < 9 THEN 3 ELSE 2 END,
       (ARRAY['Asia/Jakarta', 'Asia/Makassar', 'Asia/Jayapura', 'Asia/Tokyo'])[1 + g % 4]
FROM generate_series(1, :learners) AS g
UNION ALL
SELECT :heavy_public_id, 1, 'synthetic', 2, 'Asia/Jakarta'
"""

# How many words each learner knows: 50 to 800, scattered by a prime, or 4,000 for the heavy learner.
PLANS = """
CREATE TEMPORARY TABLE synthetic_plan ON COMMIT DROP AS
SELECT id, cohort_id, target_level,
       CASE WHEN public_id = :heavy_public_id THEN :heavy_known ELSE 50 + (id * 7919) % 751 END AS known_count
FROM learning.learners WHERE public_id LIKE 'syn-%'
"""

# The order each level's learners learn words in: easier levels first, then commonness.
WORD_ORDER = """
CREATE TEMPORARY TABLE synthetic_word_order ON COMMIT DROP AS
SELECT levels.level AS target_level, w.word_id,
       row_number() OVER (PARTITION BY levels.level ORDER BY w.level DESC, w.commonness, w.word_id) AS rank
FROM generate_series(2, 5) AS levels(level)
JOIN learning.dictionary_words w ON w.level >= levels.level
"""

MARKS = f"""
INSERT INTO learning.learning_events (learner_id, cohort_id, event_type, item_id, result, occurred_at)
SELECT p.id, p.cohort_id, {MARKED_KNOWN}, o.word_id, NULL,
       timestamptz '2026-10-05 08:00+07' + o.rank * interval '3 minutes'
FROM synthetic_plan p
JOIN synthetic_word_order o ON o.target_level = p.target_level AND o.rank <= p.known_count
"""  # noqa: S608 (constants only)

# Questions on the next words, one every 18 hours from 5 October, alternating meaning and reading.
ANSWERS = f"""
INSERT INTO learning.learning_events (learner_id, cohort_id, event_type, item_id, result, occurred_at)
SELECT p.id, p.cohort_id, {QUIZ_MEANING} + n % 2, o.word_id,
       CASE WHEN (p.id * 31 + n * 17) % 10 < 7 THEN 1 ELSE 0 END,
       timestamptz '2026-10-05 08:00+07' + n * interval '18 hours' + (p.id % 60) * interval '1 minute'
FROM synthetic_plan p
CROSS JOIN generate_series(1, :answers) AS n
JOIN synthetic_word_order o
  ON o.target_level = p.target_level AND o.rank = p.known_count + 1 + (n * 7 + p.id) % :in_progress
"""  # noqa: S608


@dataclass(frozen=True)
class SyntheticReport:
    learners: int
    events: int
    seconds: float


async def build_synthetic(app: AsyncEngine, *, learners: int = SYNTHETIC_LEARNERS) -> SyntheticReport:
    """Fill an empty, migrated app database (with its dictionary mirror synced) with synthetic learners."""
    started = time.perf_counter()
    async with app.begin() as connection:
        await connection.execute(
            text(CREATE_LEARNERS), {"learners": learners, "heavy_public_id": HEAVY_LEARNER_PUBLIC_ID}
        )
        await connection.execute(
            text(PLANS), {"heavy_public_id": HEAVY_LEARNER_PUBLIC_ID, "heavy_known": HEAVY_LEARNER_KNOWN_WORDS}
        )
        await connection.execute(text(WORD_ORDER))
        await connection.execute(text(MARKS))
        await connection.execute(text(ANSWERS), {"answers": QUIZ_ANSWERS_PER_LEARNER, "in_progress": WORDS_IN_PROGRESS})
        learner_ids = [
            int(learner_id)
            for learner_id in await connection.scalars(
                text("SELECT id FROM learning.learners WHERE public_id LIKE 'syn-%' ORDER BY id")
            )
        ]
        events = int(await connection.scalar(text("SELECT count(*) FROM learning.learning_events")) or 0)
    for start in range(0, len(learner_ids), REBUILD_BATCH):
        async with app.begin() as connection:
            await rebuild_learners(connection, learner_ids[start : start + REBUILD_BATCH])
    async with app.begin() as connection:
        await connection.execute(text("ANALYZE"))
    return SyntheticReport(learners=len(learner_ids), events=events, seconds=time.perf_counter() - started)
