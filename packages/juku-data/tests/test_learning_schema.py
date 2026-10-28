"""The learning schema: who can read what, deletion cascades, and the privacy floor on Grafana's view."""

from collections.abc import AsyncIterator
from datetime import date

import pytest
from juku_common.rules import Rules
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

SUMMARIES = ["learner_state", "learner_kanji", "learner_coverage", "learner_candidate", "learner_daily_activity"]


@pytest.fixture
async def connection(app_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection whose changes are rolled back at the end of the test."""
    async with app_engine.connect() as connection:
        transaction = await connection.begin()
        yield connection
        await transaction.rollback()


async def add_learner(connection: AsyncConnection, public_id: str) -> int:
    learner_id = await connection.scalar(
        text(
            "INSERT INTO learning.learners (public_id, nickname, target_level) "
            "VALUES (:public_id, 'nick', 5) RETURNING id"
        ),
        {"public_id": public_id},
    )
    assert isinstance(learner_id, int)
    return learner_id


@pytest.mark.parametrize("table", SUMMARIES)
async def test_the_mcp_role_can_read_each_summary(connection: AsyncConnection, table: str) -> None:
    await connection.execute(text("SET LOCAL ROLE juku_mcp"))
    await connection.execute(text(f"SELECT * FROM learning.{table} LIMIT 1"))


@pytest.mark.fitness("FF2")
async def test_the_mcp_role_cannot_read_the_event_history(connection: AsyncConnection) -> None:
    await connection.execute(text("SET LOCAL ROLE juku_mcp"))
    with pytest.raises(DBAPIError, match="permission denied"):
        await connection.execute(text("SELECT 1 FROM learning.learning_events LIMIT 1"))


async def test_the_mcp_role_cannot_read_nicknames(connection: AsyncConnection) -> None:
    await connection.execute(text("SET LOCAL ROLE juku_mcp"))
    await connection.execute(text("SELECT public_id, target_level, timezone FROM learning.learners LIMIT 1"))
    with pytest.raises(DBAPIError, match="permission denied"):
        await connection.execute(text("SELECT nickname FROM learning.learners LIMIT 1"))


async def test_the_mcp_role_cannot_write(connection: AsyncConnection) -> None:
    learner_id = await add_learner(connection, "lrn-write")
    await connection.execute(text("SET LOCAL ROLE juku_mcp"))
    with pytest.raises(DBAPIError, match="permission denied"):
        await connection.execute(text("INSERT INTO learning.learner_kanji VALUES (:id, '日', 1)"), {"id": learner_id})


async def test_deleting_a_learner_deletes_their_events_and_summaries(connection: AsyncConnection) -> None:
    learner_id = await add_learner(connection, "lrn-delete")
    await connection.execute(
        text(
            "INSERT INTO learning.learning_events (learner_id, cohort_id, event_type, item_id, occurred_at) "
            "VALUES (:id, 1, 1, 'w1', now())"
        ),
        {"id": learner_id},
    )
    await connection.execute(
        text("INSERT INTO learning.learner_state (learner_id, item_id, last_seen_at) VALUES (:id, 'w1', now())"),
        {"id": learner_id},
    )
    await connection.execute(text("DELETE FROM learning.learners WHERE id = :id"), {"id": learner_id})
    for table in ["learning_events", *SUMMARIES]:
        remaining = await connection.scalar(
            text(f"SELECT count(*) FROM learning.{table} WHERE learner_id = :id"), {"id": learner_id}
        )
        assert remaining == 0, table


@pytest.mark.guardrail("privacy.min_learners_per_cell")
async def test_the_activity_view_hides_days_with_fewer_learners_than_the_floor(
    connection: AsyncConnection, rules: Rules
) -> None:
    floor = rules.privacy.min_learners_per_cell
    for number in range(floor):
        learner_id = await add_learner(connection, f"lrn-floor-{number}")
        days = [date(2027, 1, 1), date(2027, 1, 2)] if number else [date(2027, 1, 1)]  # 2 Jan: one learner fewer
        for day in days:
            await connection.execute(
                text(
                    "INSERT INTO learning.learner_daily_activity (learner_id, day, quiz_answers) VALUES (:id, :day, 3)"
                ),
                {"id": learner_id, "day": day},
            )
    rows = (
        await connection.execute(
            text("SELECT day, active_learners FROM monitoring.activity_by_day WHERE day >= '2027-01-01' ORDER BY day")
        )
    ).all()
    assert [tuple(row) for row in rows] == [(date(2027, 1, 1), floor)]


async def test_events_have_monthly_partitions_through_2027(connection: AsyncConnection) -> None:
    partitions = await connection.scalar(
        text("SELECT count(*) FROM pg_inherits WHERE inhparent = 'learning.learning_events'::regclass")
    )
    assert partitions == 15
