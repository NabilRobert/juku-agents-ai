"""Hapus data saya and Unduh data saya (Phase 2, privacy; UU PDP's deletion and access).

Every table that holds a learner's rows has a `learner_id` column; both
functions find those tables in the catalog, so a table added later is
covered without a change here.

Deleting removes the learner's row, and the foreign keys cascade through
learning state, consent, chat text, ratings and their invite code. The
two records kept for totals, the per-call records and the model costs,
keep their rows with the learner ID set to NULL, so spend and tool counts
still add up (Phase 2, deletion). Backups age out within 7 days.

The export is every row with the learner's ID, as JSON, with internal
IDs left out where they'd mean nothing to the learner.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

TABLES_WITH_LEARNERS = """
SELECT n.nspname, c.relname FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE a.attname = 'learner_id' AND NOT a.attisdropped
  AND c.relkind IN ('r', 'p') AND NOT c.relispartition
  AND n.nspname IN ('learning', 'app', 'monitoring')
ORDER BY 1, 2
"""
# Kept for totals, with the learner's ID removed rather than the row.
KEEP_ANONYMOUS = ("monitoring.tool_calls", "app.model_calls")
LEARNER_FIELDS = "public_id, cohort_id, nickname, target_level, exam_date, timezone, created_at, last_active_at"


def _count_rows(table: str) -> str:
    return f"SELECT count(*) FROM {table} WHERE learner_id = :id"  # noqa: S608 (a table name from the catalog)


def _remove_learner(table: str) -> str:
    return f"UPDATE {table} SET learner_id = NULL WHERE learner_id = :id"  # noqa: S608 (a constant table name)


def _select_rows(table: str) -> str:
    return f"SELECT * FROM {table} WHERE learner_id = :id"  # noqa: S608 (a table name from the catalog)


LEARNER_ROW = f"SELECT {LEARNER_FIELDS} FROM learning.learners WHERE id = :id"  # noqa: S608 (a constant)


async def _learner_tables(connection: AsyncConnection) -> list[str]:
    """Every table with a learner_id column: partitioned parents, not their partitions."""
    rows = (await connection.execute(text(TABLES_WITH_LEARNERS))).all()
    return [f"{schema}.{table}" for schema, table in rows]


async def delete_learner(engine: AsyncEngine, learner_id: int) -> dict[str, int]:
    """Delete everything about the learner; return how many rows each table lost or anonymised."""
    counts: dict[str, int] = {}
    async with engine.begin() as connection:
        for table in await _learner_tables(connection):
            count = int(await connection.scalar(text(_count_rows(table)), {"id": learner_id}) or 0)
            if count:
                counts[table] = count
        for table in KEEP_ANONYMOUS:
            await connection.execute(
                text(_remove_learner(table)),
                {"id": learner_id},
            )
        await connection.execute(text("DELETE FROM learning.learners WHERE id = :id"), {"id": learner_id})
    return counts


def _plain(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


async def export_learner(engine: AsyncEngine, learner_id: int) -> dict[str, Any]:
    """Everything Juku holds about the learner, as JSON-ready data."""
    async with engine.connect() as connection:
        learner = (
            (
                await connection.execute(
                    text(LEARNER_ROW),
                    {"id": learner_id},
                )
            )
            .mappings()
            .one()
        )
        tables: dict[str, list[dict[str, Any]]] = {}
        for table in await _learner_tables(connection):
            rows = (await connection.execute(text(_select_rows(table)), {"id": learner_id})).mappings().all()
            tables[table] = [
                {column: _plain(value) for column, value in row.items() if column not in ("learner_id", "id")}
                for row in rows
            ]
    return {"learner": {field: _plain(value) for field, value in learner.items()}, "tables": tables}
