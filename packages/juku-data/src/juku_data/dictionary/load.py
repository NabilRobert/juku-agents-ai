"""Load the pinned OpenJLPT build into the `dict` database (slice 1, D1-D4).

One call rebuilds the whole dictionary:
1. read the (already checksummed) SQLite file;
2. COPY its tables into a fresh `ojlpt_staging` schema, then add keys;
3. build the derived tables: each word's kanji, its level and commonness,
   kanji leverage (ADR-010), the supplement words, and the reading index;
4. comment every table and view, for the model reading it through
   MCP-backbone (D4);
5. compare the word IDs with the current `ojlpt` schema and report any
   that disappeared (the update policy);
6. swap `ojlpt_staging` in for `ojlpt` in the same transaction, so readers
   see the old dictionary or the new one, never half of one.

This is plain Python over asyncpg's COPY rather than pgloader: the load
needs transforms pgloader doesn't do (levels as numbers, unnested examples,
SudachiPy's index), and asyncpg is already in the stack (ADR-026).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_data.dictionary.pin import OPENJLPT_COMMIT
from juku_data.dictionary.read_sqlite import OpenJlptRows, read_openjlpt
from juku_data.dictionary.schema import BASE_TABLES_SQL, DERIVED_SQL, KEYS_SQL, TABLE_COMMENTS, VIEWS_SQL
from juku_data.dictionary.sentences import DictionaryWord, ReadingIndex, SourceSentence, build_reading_index
from juku_data.dictionary.source import DictionaryError, SourceFiles
from juku_data.dictionary.supplement import SupplementWord, read_supplement

LIVE_SCHEMA = "ojlpt"
STAGING_SCHEMA = "ojlpt_staging"
READER_ROLE = "dict_reader"


@dataclass(frozen=True)
class LoadReport:
    commit: str
    row_counts: dict[str, int]
    table_md5: dict[str, str]
    disappeared_ids: list[str] = field(default_factory=list[str])
    sentences_total: int = 0
    sentences_mapped: int = 0
    content_tokens: int = 0
    content_tokens_mapped: int = 0
    seconds: float = 0.0


def _dictionary_words(rows: OpenJlptRows, supplement: list[SupplementWord]) -> list[DictionaryWord]:
    words = [
        DictionaryWord(
            id=row[0],
            spellings=(row[1], *json.loads(row[8])),
            readings=(row[2], *json.loads(row[9])),
        )
        for row in rows.vocab
    ]
    words += [DictionaryWord(id=word.id, spellings=(word.word,), readings=(word.reading,)) for word in supplement]
    return words


def _source_sentences(rows: OpenJlptRows) -> list[SourceSentence]:
    """Each example once, by its text, in a fixed order so sentence IDs are stable for one build."""
    by_text: dict[str, SourceSentence] = {}
    for _, _, ja, furigana, en, tatoeba_id in sorted(rows.vocab_example, key=lambda row: (row[2], row[0], row[1])):
        by_text.setdefault(ja, SourceSentence(ja, furigana, en, tatoeba_id))
    return list(by_text.values())


async def _driver(connection: AsyncConnection) -> Any:
    """asyncpg's own connection, for COPY and for multi-statement scripts."""
    raw = await connection.get_raw_connection()
    driver = raw.driver_connection
    if driver is None:
        raise DictionaryError("the dict database connection has no driver connection")
    return driver


async def _execute_script(connection: AsyncConnection, script: str) -> None:
    await (await _driver(connection)).execute(script)


async def _copy(connection: AsyncConnection, table: str, records: list[tuple[Any, ...]]) -> None:
    await (await _driver(connection)).copy_records_to_table(table, schema_name=STAGING_SCHEMA, records=records)


async def _disappeared_ids(connection: AsyncConnection) -> list[str]:
    exists = await connection.scalar(text("SELECT to_regclass(:name) IS NOT NULL"), {"name": f"{LIVE_SCHEMA}.vocab"})
    if not exists:
        return []
    found = await connection.scalars(
        text(
            f"(SELECT id FROM {LIVE_SCHEMA}.vocab EXCEPT SELECT id FROM {STAGING_SCHEMA}.vocab) "  # noqa: S608
            f"UNION ALL (SELECT id FROM {LIVE_SCHEMA}.supplement_word "
            f"EXCEPT SELECT id FROM {STAGING_SCHEMA}.supplement_word) ORDER BY 1"
        )
    )
    return list(found)


async def _table_md5(connection: AsyncConnection, table: str) -> str:
    value = await connection.scalar(
        text(f"SELECT md5(string_agg(t::text, E'\\n' ORDER BY t::text)) FROM {STAGING_SCHEMA}.{table} t")  # noqa: S608
    )
    return str(value)


async def _load_reading_index(connection: AsyncConnection, index: ReadingIndex) -> None:
    await _copy(
        connection,
        "sentence",
        [
            (
                sentence.sentence_id,
                sentence.source.ja,
                sentence.source.furigana,
                sentence.source.en,
                sentence.source.tatoeba_id,
                len(sentence.word_ids),
            )
            for sentence in index.sentences
        ],
    )
    await _copy(
        connection,
        "sentence_word",
        [(sentence.sentence_id, word_id) for sentence in index.sentences for word_id in sorted(sentence.word_ids)],
    )


async def _copy_source_tables(
    connection: AsyncConnection, rows: OpenJlptRows, supplement: list[SupplementWord]
) -> None:
    for table, records in (
        ("vocab", rows.vocab),
        ("vocab_example", rows.vocab_example),
        ("kanji", rows.kanji),
        ("grammar", rows.grammar),
        ("pos", rows.pos),
    ):
        await _copy(connection, table, records)
    await _copy(
        connection,
        "supplement_word",
        [(word.id, word.word, word.reading, word.jmdict_id, word.meanings) for word in supplement],
    )


async def _record_meta(
    connection: AsyncConnection, commit: str, source: SourceFiles, index: ReadingIndex | None
) -> None:
    """Which build this is; the sentence counts are unknown when the reading index was skipped."""
    await connection.execute(
        text(
            "INSERT INTO meta (openjlpt_commit, sqlite_sha256, sentences_total, content_tokens, "
            "content_tokens_mapped) VALUES (:commit, :sha, :sentences, :tokens, :mapped)"
        ),
        {
            "commit": commit,
            "sha": source.sqlite_sha256,
            "sentences": index.sentences_total if index else None,
            "tokens": index.content_tokens if index else None,
            "mapped": index.content_tokens_mapped if index else None,
        },
    )


async def _comment_tables(connection: AsyncConnection) -> None:
    for table, comment in TABLE_COMMENTS.items():
        kind = "VIEW" if table.endswith("_overview") else "TABLE"
        await connection.execute(text(f"COMMENT ON {kind} {table} IS '{comment.replace("'", "''")}'"))


async def _swap_staging_in(connection: AsyncConnection) -> None:
    await connection.execute(text(f"DROP SCHEMA IF EXISTS {LIVE_SCHEMA} CASCADE"))
    await connection.execute(text(f"ALTER SCHEMA {STAGING_SCHEMA} RENAME TO {LIVE_SCHEMA}"))
    await connection.execute(text(f"GRANT USAGE ON SCHEMA {LIVE_SCHEMA} TO {READER_ROLE}"))
    await connection.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA {LIVE_SCHEMA} TO {READER_ROLE}"))


async def load_dictionary(
    engine: AsyncEngine, source: SourceFiles, *, commit: str = OPENJLPT_COMMIT, with_reading_index: bool = True
) -> LoadReport:
    """Rebuild the dictionary from `source` and swap it in. `with_reading_index=False` skips SudachiPy (tests)."""
    started = time.perf_counter()
    rows = read_openjlpt(source.sqlite_path)
    supplement = read_supplement()
    index = (
        build_reading_index(_dictionary_words(rows, supplement), _source_sentences(rows))
        if with_reading_index
        else ReadingIndex()
    )
    async with engine.begin() as connection:
        await connection.execute(text(f"DROP SCHEMA IF EXISTS {STAGING_SCHEMA} CASCADE"))
        await connection.execute(text(f"CREATE SCHEMA {STAGING_SCHEMA}"))
        await connection.execute(text(f"SET LOCAL search_path = {STAGING_SCHEMA}"))
        await _execute_script(connection, BASE_TABLES_SQL)
        await _copy_source_tables(connection, rows, supplement)
        await _load_reading_index(connection, index)
        await _record_meta(connection, commit, source, index if with_reading_index else None)
        await _execute_script(connection, KEYS_SQL)
        await _execute_script(connection, DERIVED_SQL)
        await _execute_script(connection, VIEWS_SQL)
        await _comment_tables(connection)
        await connection.execute(text("ANALYZE"))
        row_counts = rows.counts()
        table_md5 = {table: await _table_md5(connection, table) for table in row_counts}
        disappeared = await _disappeared_ids(connection)
        await _swap_staging_in(connection)
    return LoadReport(
        commit=commit,
        row_counts=row_counts,
        table_md5=table_md5,
        disappeared_ids=disappeared,
        sentences_total=index.sentences_total,
        sentences_mapped=len(index.sentences),
        content_tokens=index.content_tokens,
        content_tokens_mapped=index.content_tokens_mapped,
        seconds=time.perf_counter() - started,
    )
