"""FF3: the summaries kept as events arrive equal a full recompute from the events."""

import random
from datetime import UTC, datetime, timedelta

import pytest
from fixture_learners import FixtureLearner
from juku_data.engine import Databases, create_learner, mark_known, unmark_known, verify_state
from juku_data.engine.api import record_quiz_answer
from juku_data.engine.models import Learner, QuizKind
from sqlalchemy import text

WORKLOAD_SEED = 20261028
WORKLOAD_EVENTS = 400


@pytest.mark.fitness("FF3")
async def test_the_fixture_learners_summaries_equal_a_recompute(
    engine_databases: Databases, fixtures_and_learners: dict[str, tuple[FixtureLearner, Learner]]
) -> None:
    learner_ids = [learner.id for _, learner in fixtures_and_learners.values()]
    assert await verify_state(engine_databases, learner_ids) == []


async def some_words(db: Databases, count: int) -> list[str]:
    async with db.app.connect() as connection:
        found = await connection.scalars(
            text("SELECT word_id FROM learning.dictionary_words WHERE level >= 4 ORDER BY md5(word_id) LIMIT :n"),
            {"n": count},
        )
        return list(found)


@pytest.mark.fitness("FF3")
async def test_a_random_workload_leaves_summaries_equal_to_a_recompute(engine_databases: Databases) -> None:
    """Marks, unmarks and answers in a seeded random order, across timezones and a midnight."""
    chooser = random.Random(WORKLOAD_SEED)  # noqa: S311 (a reproducible workload, not a secret)
    words = await some_words(engine_databases, 40)
    learners = [
        await create_learner(engine_databases, nickname="w", target_level=level, timezone=zone)
        for level, zone in ((5, "Asia/Jakarta"), (4, "Asia/Makassar"), (3, "Asia/Tokyo"))
    ]
    at = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)
    for _ in range(WORKLOAD_EVENTS):
        at += timedelta(minutes=chooser.choice([7, 45, 180, 600]))
        learner, word = chooser.choice(learners), chooser.choice(words)
        action = chooser.random()
        if action < 0.15:
            await mark_known(engine_databases, learner.id, word, at)
        elif action < 0.25:
            await unmark_known(engine_databases, learner.id, word, at)
        else:
            kind: QuizKind = "meaning" if chooser.random() < 0.5 else "reading"
            await record_quiz_answer(engine_databases, learner.id, word, kind, chooser.random() < 0.7, at)
    assert await verify_state(engine_databases, [learner.id for learner in learners]) == []


@pytest.mark.fitness("FF3")
async def test_a_summary_that_drifts_from_the_events_is_reported(engine_databases: Databases) -> None:
    """The check isn't vacuous: change one summary row behind the engine's back and it's found."""
    learner = await create_learner(engine_databases, nickname="drift", target_level=5)
    word = (await some_words(engine_databases, 1))[0]
    try:
        await mark_known(engine_databases, learner.id, word, datetime(2026, 11, 2, tzinfo=UTC))
        async with engine_databases.app.begin() as connection:
            await connection.execute(
                text("UPDATE learning.learner_coverage SET words_known = words_known + 1 WHERE learner_id = :id"),
                {"id": learner.id},
            )
        differences = await verify_state(engine_databases, [learner.id])
        assert differences and all("learner_coverage" in difference for difference in differences)
    finally:
        # Other tests verify every learner in the database; this one mustn't stay drifted.
        async with engine_databases.app.begin() as connection:
            await connection.execute(text("DELETE FROM learning.learners WHERE id = :id"), {"id": learner.id})
