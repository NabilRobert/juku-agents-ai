"""Deletion and export (Phase 2, privacy; standard checks, "deletion and export")."""

from datetime import UTC, datetime

import pytest
from juku_app.privacy import delete_learner, export_learner
from juku_data.engine import Databases, create_learner, mark_known
from juku_data.engine.models import Learner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LEARNER_COLUMNS = """
SELECT n.nspname, c.relname FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE a.attname = 'learner_id' AND NOT a.attisdropped
  AND c.relkind IN ('r', 'p') AND NOT c.relispartition
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY 1, 2
"""


async def fill(db: Databases, learner: Learner) -> None:
    """Something of the learner's in every kind of table."""
    async with db.app.connect() as connection:
        word = str(
            await connection.scalar(text("SELECT word_id FROM learning.dictionary_words ORDER BY word_id LIMIT 1"))
        )
    await mark_known(db, learner.id, word, datetime(2026, 11, 2, tzinfo=UTC))
    async with db.app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.consents (learner_id, version, is_adult, accepts_service, accepts_aggregates) "
                "VALUES (:id, 'v', true, true, false)"
            ),
            {"id": learner.id},
        )
        await connection.execute(
            text(
                "INSERT INTO app.chat_messages (learner_id, role, body, expires_at) "
                "VALUES (:id, 'learner', 'kenapa?', now() + interval '60 days')"
            ),
            {"id": learner.id},
        )
        await connection.execute(
            text(
                "INSERT INTO app.model_calls (pool, learner_id, requests, input_tokens, output_tokens, cost_usd) "
                "VALUES ('chat', :id, 1, 10, 10, 0.000001)"
            ),
            {"id": learner.id},
        )
        await connection.execute(
            text(
                "INSERT INTO app.ratings (learner_id, target_kind, target_id, is_helpful) VALUES (:id, 'chat', 1, true)"
            ),
            {"id": learner.id},
        )
        await connection.execute(
            text(
                "INSERT INTO monitoring.tool_calls (called_at, agent, server, tool, duration_ms, outcome, learner_id) "
                "VALUES (now(), 'shiori', 'juku', 'get_progress', 5, 'ok', :id)"
            ),
            {"id": learner.id},
        )


async def rows_left(engine: AsyncEngine, learner_id: int) -> dict[str, int]:
    found: dict[str, int] = {}
    async with engine.connect() as connection:
        quote = connection.dialect.identifier_preparer.quote
        for schema, table in (await connection.execute(text(LEARNER_COLUMNS))).all():
            count = await connection.scalar(
                text(f"SELECT count(*) FROM {quote(schema)}.{quote(table)} WHERE learner_id = :id"),
                {"id": learner_id},
            )
            if count:
                found[f"{schema}.{table}"] = int(count)
    return found


async def test_deleting_leaves_no_row_with_the_learners_id_anywhere(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="leaving", target_level=5)
    await fill(engine_databases, learner)
    assert len(await rows_left(engine_databases.app, learner.id)) >= 5
    await delete_learner(engine_databases.app, learner.id)
    assert await rows_left(engine_databases.app, learner.id) == {}
    async with engine_databases.app.connect() as connection:
        assert (
            await connection.scalar(text("SELECT count(*) FROM learning.learners WHERE id = :id"), {"id": learner.id})
            == 0
        )


async def test_totals_still_add_up_after_a_deletion(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="leaving", target_level=5)
    await fill(engine_databases, learner)
    async with engine_databases.app.connect() as connection:
        calls_before = await connection.scalar(text("SELECT count(*) FROM monitoring.tool_calls"))
        cost_before = await connection.scalar(text("SELECT sum(cost_usd) FROM app.model_calls"))
    await delete_learner(engine_databases.app, learner.id)
    async with engine_databases.app.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM monitoring.tool_calls")) == calls_before
        assert await connection.scalar(text("SELECT sum(cost_usd) FROM app.model_calls")) == cost_before


async def test_an_export_holds_every_row_of_the_learners_and_no_one_elses(engine_databases: Databases) -> None:
    mine = await create_learner(engine_databases, nickname="me", target_level=5)
    other = await create_learner(engine_databases, nickname="other", target_level=5)
    await fill(engine_databases, mine)
    await fill(engine_databases, other)
    export = await export_learner(engine_databases.app, mine.id)
    assert export["learner"]["public_id"] == mine.public_id
    assert "id" not in export["learner"], "internal IDs never leave the database"
    tables = export["tables"]
    for table, count in (await rows_left(engine_databases.app, mine.id)).items():
        assert len(tables[table]) == count, table
    exported = str(export)
    assert other.public_id not in exported
    assert "kenapa?" in exported


# Uppercase, a space and a double quote: a table name that only works quoted, and escaped.
AWKWARD_TABLE = 'Catatan "Lama" v2'


@pytest.mark.xfail(strict=True, reason="EDD: quoting the catalog's names lands in the next commit")
async def test_a_learner_table_whose_name_needs_quoting_is_still_exported_and_deleted(
    engine_databases: Databases,
) -> None:
    """privacy.py builds its SQL from the catalog's names; they're quoted as identifiers, and values stay bound."""
    learner = await create_learner(engine_databases, nickname="awkward", target_level=5)
    async with engine_databases.app.begin() as connection:
        table = f"app.{connection.dialect.identifier_preparer.quote(AWKWARD_TABLE)}"
        await connection.execute(
            text(
                f"CREATE TABLE {table} (learner_id bigint NOT NULL "
                "REFERENCES learning.learners (id) ON DELETE CASCADE, note text NOT NULL)"
            )
        )
        await connection.execute(
            text(f"INSERT INTO {table} (learner_id, note) VALUES (:id, 'catatan lama')"),
            {"id": learner.id},
        )
    try:
        exported = await export_learner(engine_databases.app, learner.id)
        assert exported["tables"][table] == [{"note": "catatan lama"}]
        removed = await delete_learner(engine_databases.app, learner.id)
        assert removed[table] == 1
        assert await rows_left(engine_databases.app, learner.id) == {}
    finally:
        async with engine_databases.app.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
