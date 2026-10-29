"""FF3 in production: the nightly job passes on consistent summaries and fails, recorded, on drift."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from juku_data.engine import Databases, create_learner, mark_known
from juku_ops.state_check import StateDriftError, verify_production_state
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def learner_id(engine_databases: Databases) -> AsyncIterator[int]:
    learner = await create_learner(engine_databases, nickname="nightly", target_level=5)
    async with engine_databases.app.connect() as connection:
        word = await connection.scalar(text("SELECT word_id FROM learning.dictionary_words ORDER BY word_id LIMIT 1"))
    await mark_known(engine_databases, learner.id, str(word), datetime(2026, 11, 2, tzinfo=UTC))
    yield learner.id
    async with engine_databases.app.begin() as connection:
        await connection.execute(text("DELETE FROM learning.learners WHERE id = :id"), {"id": learner.id})


async def latest_run(engine: AsyncEngine) -> tuple[str, str | None]:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT status, error_category FROM monitoring.job_runs WHERE job = 'verify-state' "
                    "ORDER BY id DESC LIMIT 1"
                )
            )
        ).one()
    return str(row[0]), row[1]


@pytest.mark.fitness("FF3")
async def test_consistent_summaries_pass_and_the_run_is_recorded(engine_databases: Databases, learner_id: int) -> None:
    assert learner_id
    assert await verify_production_state(engine_databases.app, engine_databases.app) == []
    assert await latest_run(engine_databases.app) == ("succeeded", None)


@pytest.mark.fitness("FF3")
async def test_drifted_summaries_fail_the_job_and_say_so(engine_databases: Databases, learner_id: int) -> None:
    async with engine_databases.app.begin() as connection:
        await connection.execute(
            text("UPDATE learning.learner_state SET correct_count = 99 WHERE learner_id = :id"), {"id": learner_id}
        )
    with pytest.raises(StateDriftError, match="differences"):
        await verify_production_state(engine_databases.app, engine_databases.app)
    assert await latest_run(engine_databases.app) == ("failed", "StateDriftError")
