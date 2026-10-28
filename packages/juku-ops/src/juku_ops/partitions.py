"""Monthly partitions, created ahead of time (scale path, the data design).

Every range-partitioned table in the database is partitioned by month:
the per-call records here, and the learning events and pipeline runs from
later slices. Rows for a month with no partition would fail to insert, so
the daily `juku-ops ensure-partitions` job keeps MONTHS_AHEAD months ready.
It finds the tables in the catalog, so a new partitioned table needs no
change here. Partitions are named `<table>_YYYY_MM`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

MONTHS_AHEAD = 3

_RANGE_PARTITIONED_TABLES = text("""
    SELECT n.nspname AS schema_name, c.relname AS table_name
    FROM pg_partitioned_table p
    JOIN pg_class c ON c.oid = p.partrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE p.partstrat = 'r' AND NOT c.relispartition
    ORDER BY 1, 2
""")

_PARTITION_EXISTS = text("SELECT to_regclass(:qualified_name) IS NOT NULL")


def first_of_next_month(day: date) -> date:
    return date(day.year + 1, 1, 1) if day.month == 12 else date(day.year, day.month + 1, 1)


def months_from(today: date, count: int) -> list[date]:
    """The first day of this month and the `count` months after it."""
    months = [date(today.year, today.month, 1)]
    for _ in range(count):
        months.append(first_of_next_month(months[-1]))
    return months


async def ensure_month_partitions(engine: AsyncEngine, today: date) -> list[str]:
    """Create any missing partition from this month to MONTHS_AHEAD months on; return the new ones' names."""
    created: list[str] = []
    async with engine.begin() as connection:
        tables = (await connection.execute(_RANGE_PARTITIONED_TABLES)).all()
        for schema_name, table_name in tables:
            for month in months_from(today, MONTHS_AHEAD):
                partition = f'"{schema_name}"."{table_name}_{month:%Y_%m}"'
                if await connection.scalar(_PARTITION_EXISTS, {"qualified_name": partition}):
                    continue
                await connection.execute(
                    text(
                        f'CREATE TABLE {partition} PARTITION OF "{schema_name}"."{table_name}" '
                        f"FOR VALUES FROM ('{month}') TO ('{first_of_next_month(month)}')"
                    )
                )
                created.append(f"{schema_name}.{table_name}_{month:%Y_%m}")
    return created
