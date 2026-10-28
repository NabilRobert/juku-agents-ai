"""The monitoring schema migration: it applies, reverses, and Grafana can only read it."""

import asyncio

import pytest
from juku_testkit.databases import TestDatabase, create_roles, migrate_to_heads
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

MONITORING_TABLES = {"tool_calls", "audit_lines", "audit_imports", "heartbeats", "job_runs", "expected_jobs"}


async def monitoring_tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as connection:
        rows = await connection.execute(
            text(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'monitoring' AND c.relkind IN ('r', 'p') AND NOT c.relispartition"
            )
        )
        return {str(row[0]) for row in rows}


async def test_the_migration_applies_reverses_and_applies_again(empty_database: TestDatabase) -> None:
    from alembic import command
    from alembic.config import Config
    from juku_testkit.databases import repo_root

    # Alembic and the role setup run their own event loops, so they run in a thread here.
    await asyncio.to_thread(create_roles)
    await asyncio.to_thread(migrate_to_heads, empty_database)
    engine = create_async_engine(empty_database.sqlalchemy_url)
    try:
        assert MONITORING_TABLES <= await monitoring_tables(engine)
        config = Config(str(repo_root() / "alembic.ini"))
        config.attributes["database_url"] = empty_database.sqlalchemy_url
        await asyncio.to_thread(command.downgrade, config, "monitoring@base")
        assert await monitoring_tables(engine) == set()
        await asyncio.to_thread(migrate_to_heads, empty_database)
        assert MONITORING_TABLES <= await monitoring_tables(engine)
    finally:
        await engine.dispose()


async def test_tool_calls_has_monthly_partitions_through_2027(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as connection:
        partitions = await connection.scalar(
            text("SELECT count(*) FROM pg_inherits WHERE inhparent = 'monitoring.tool_calls'::regclass")
        )
    assert partitions == 15


async def test_grafana_reader_can_read_the_monitoring_schema(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as connection:
        await connection.execute(text("SET ROLE grafana_reader"))
        assert await connection.scalar(text("SELECT count(*) FROM monitoring.expected_jobs")) == 2
        await connection.rollback()


async def test_grafana_reader_cannot_write(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as connection:
        await connection.execute(text("SET ROLE grafana_reader"))
        with pytest.raises(DBAPIError, match="permission denied"):
            await connection.execute(text("INSERT INTO monitoring.heartbeats (source, beat_at) VALUES ('x', now())"))
        await connection.rollback()


async def test_the_app_can_record_a_tool_call_but_not_read_others(app_engine: AsyncEngine) -> None:
    async with app_engine.connect() as connection:
        await connection.execute(text("SET ROLE juku_app"))
        await connection.execute(
            text(
                "INSERT INTO monitoring.tool_calls (called_at, agent, server, tool, duration_ms, outcome) "
                "VALUES (now(), 'shiori', 'juku', 'get_progress', 12, 'ok')"
            )
        )
        with pytest.raises(DBAPIError, match="permission denied"):
            await connection.execute(text("SELECT * FROM monitoring.tool_calls"))
        await connection.rollback()
