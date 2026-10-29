"""The cron jobs: job-run records, the heartbeat and partition upkeep."""

from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
from juku_ops.heartbeat import beat, is_healthy
from juku_ops.jobs import recorded_run
from juku_ops.partitions import ensure_month_partitions, months_from
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def engine(app_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with app_engine.begin() as connection:
        await connection.execute(text("TRUNCATE monitoring.job_runs, monitoring.heartbeats"))
    yield app_engine


async def latest_run(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT format('%s %s %s', job, status, coalesce(error_category, '-')), finished_at IS NOT NULL "
                    "FROM monitoring.job_runs ORDER BY id DESC LIMIT 1"
                )
            )
        ).one()
    return f"{row[0]} finished={row[1]}"


async def test_a_job_that_succeeds_records_its_start_and_end(engine: AsyncEngine) -> None:
    async with recorded_run(engine, "import-audit"):
        pass
    assert await latest_run(engine) == "import-audit succeeded - finished=True"


async def test_a_job_that_fails_records_the_error_class_and_still_raises(engine: AsyncEngine) -> None:
    with pytest.raises(TimeoutError):
        async with recorded_run(engine, "import-audit"):
            raise TimeoutError("the upstream hung")
    assert await latest_run(engine) == "import-audit failed TimeoutError finished=True"


async def test_a_beat_records_the_time_and_a_second_beat_moves_it(engine: AsyncEngine) -> None:
    await beat(engine, "app")
    await beat(engine, "app")
    async with engine.connect() as connection:
        count = await connection.scalar(text("SELECT count(*) FROM monitoring.heartbeats WHERE source = 'app'"))
        age = await connection.scalar(text("SELECT now() - beat_at < interval '1 minute' FROM monitoring.heartbeats"))
    assert (count, age) == (1, True)


def respond_with(status: int) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(status)))


def fail_to_connect() -> httpx.AsyncClient:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.AsyncClient(transport=httpx.MockTransport(refuse))


async def test_the_app_is_healthy_only_when_it_answers_200() -> None:
    assert await is_healthy(respond_with(200), "http://app/healthz")
    assert not await is_healthy(respond_with(503), "http://app/healthz")
    assert not await is_healthy(fail_to_connect(), "http://app/healthz")


def test_months_from_crosses_the_year_end() -> None:
    assert months_from(date(2027, 11, 20), 3) == [
        date(2027, 11, 1),
        date(2027, 12, 1),
        date(2028, 1, 1),
        date(2028, 2, 1),
    ]


async def test_missing_partitions_are_created_and_existing_ones_left_alone(engine: AsyncEngine) -> None:
    created = await ensure_month_partitions(engine, date(2027, 11, 20))
    try:
        assert {"monitoring.tool_calls_2028_01", "monitoring.tool_calls_2028_02"} <= set(created)
        assert not any(name.endswith(("_2027_11", "_2027_12")) for name in created), "those exist already"
        assert await ensure_month_partitions(engine, date(2027, 11, 20)) == []
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO monitoring.tool_calls (called_at, agent, server, tool, duration_ms, outcome) "
                    "VALUES ('2028-02-10T12:00:00Z', 'shiori', 'juku', 'get_progress', 9, 'ok')"
                )
            )
    finally:
        async with engine.begin() as connection:
            for name in created:
                await connection.execute(text(f"DROP TABLE {name}"))
