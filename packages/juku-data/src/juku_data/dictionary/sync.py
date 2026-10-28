"""Mirror the dictionary's index columns into the app database (ADR-026).

Learner state is computed in the app database, and Postgres can't join
across databases, so the few dictionary columns the summaries need are
copied there: each word's level and commonness, each word's kanji, each
kanji's level, and kanji leverage. About 34,000 small rows, replaced in one
transaction after every dictionary load, with the build they came from.

It also reports words learners have in their state that the new
dictionary lacks (standard checks, "a dictionary upgrade"): OpenJLPT's IDs
are stable, so the list should be empty; if not, it is listed, not hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

MIRRORS = (
    ("dictionary_words", "SELECT id, level, commonness FROM ojlpt.word_level ORDER BY id"),
    ("dictionary_word_kanji", "SELECT id, kanji FROM ojlpt.word_kanji ORDER BY id, kanji"),
    ("dictionary_kanji", "SELECT character, level FROM ojlpt.kanji ORDER BY character"),
    ("kanji_leverage", "SELECT kanji, level, words FROM ojlpt.kanji_leverage ORDER BY kanji, level"),
)
KNOWN_IDS = "SELECT id FROM ojlpt.vocab UNION SELECT id FROM ojlpt.supplement_word"


@dataclass(frozen=True)
class SyncReport:
    words: int
    word_kanji: int
    kanji: int
    leverage_rows: int
    items_missing_from_dictionary: list[str] = field(default_factory=list[str])


async def _copy(connection: AsyncConnection, table: str, records: list[tuple[Any, ...]]) -> None:
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    if driver is None:
        raise RuntimeError("the app database connection has no driver connection")
    await driver.copy_records_to_table(table, schema_name="learning", records=records)


async def sync_index(dict_engine: AsyncEngine, app_engine: AsyncEngine) -> SyncReport:
    """Replace the app database's mirror with the dict database's current build."""
    async with dict_engine.connect() as source:
        mirrored = {table: [tuple(row) for row in await source.execute(text(query))] for table, query in MIRRORS}
        commit, sqlite_sha256 = (
            await source.execute(text("SELECT openjlpt_commit, sqlite_sha256 FROM ojlpt.meta"))
        ).one()
        dictionary_ids = set(await source.scalars(text(KNOWN_IDS)))
    async with app_engine.begin() as target:
        await target.execute(
            text(f"TRUNCATE {', '.join(f'learning.{table}' for table, _ in MIRRORS)}, learning.dictionary_version")
        )
        for table, records in mirrored.items():
            await _copy(target, table, records)
        await target.execute(
            text("INSERT INTO learning.dictionary_version (openjlpt_commit, sqlite_sha256) VALUES (:commit, :sha)"),
            {"commit": commit, "sha": sqlite_sha256},
        )
        learner_items = set(await target.scalars(text("SELECT DISTINCT item_id FROM learning.learner_state")))
    return SyncReport(
        words=len(mirrored["dictionary_words"]),
        word_kanji=len(mirrored["dictionary_word_kanji"]),
        kanji=len(mirrored["dictionary_kanji"]),
        leverage_rows=len(mirrored["kanji_leverage"]),
        items_missing_from_dictionary=sorted(learner_items - dictionary_ids),
    )
