"""Fitness function FF9's probe: find planted text anywhere in a schema.

A test plants a recognisable string (a fake question) in what a component
receives, lets it write its records, then asks where the string ended up.
Every text-like column of every table in the schema is searched, so a new
column can't leak content unnoticed.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

PLANTED_QUESTION = "kenapa saya selalu salah baca 生? PLANTED-7f3a"

_TEXT_COLUMNS = text("""
    SELECT c.table_name, c.column_name
    FROM information_schema.columns c
    JOIN information_schema.tables t USING (table_schema, table_name)
    WHERE c.table_schema = :schema AND t.table_type = 'BASE TABLE'
      AND c.data_type IN ('text', 'character varying', 'jsonb', 'json', 'ARRAY')
    ORDER BY 1, 2
""")


async def find_text(connection: AsyncConnection, schema: str, needle: str) -> list[str]:
    """`table.column` for every column in `schema` that contains `needle` in any row."""
    found: list[str] = []
    columns = (await connection.execute(_TEXT_COLUMNS, {"schema": schema})).all()
    for table_name, column_name in columns:
        query = text(
            f'SELECT EXISTS (SELECT 1 FROM "{schema}"."{table_name}" '  # noqa: S608 (names from the catalog)
            f'WHERE "{column_name}"::text LIKE :pattern)'
        )
        if await connection.scalar(query, {"pattern": f"%{needle}%"}):
            found.append(f"{table_name}.{column_name}")
    return found
