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
from juku_data.dictionary.sentences import DictionaryWord, ReadingIndex, SourceSentence, build_reading_index
from juku_data.dictionary.source import DictionaryError, SourceFiles
from juku_data.dictionary.supplement import SupplementWord, read_supplement

LIVE_SCHEMA = "ojlpt"
STAGING_SCHEMA = "ojlpt_staging"
READER_ROLE = "dict_reader"

BASE_TABLES_SQL = """
CREATE TABLE vocab (
    id text NOT NULL, word text NOT NULL, reading text NOT NULL, romaji text NOT NULL, meanings jsonb NOT NULL,
    level smallint NOT NULL, pos jsonb NOT NULL, jmdict_id integer, other_forms jsonb NOT NULL,
    other_readings jsonb NOT NULL, examples jsonb NOT NULL);
CREATE TABLE vocab_example (
    vocab_id text NOT NULL, ord smallint NOT NULL, ja text NOT NULL, furigana text, en text, tatoeba_id integer);
CREATE TABLE kanji (
    character text NOT NULL, level smallint NOT NULL, strokes smallint, grade smallint, freq smallint,
    radical text, radical_number smallint, onyomi jsonb NOT NULL, kunyomi jsonb NOT NULL, nanori jsonb NOT NULL,
    meanings jsonb NOT NULL, words jsonb NOT NULL, supplementary boolean NOT NULL);
CREATE TABLE grammar (
    id text NOT NULL, pattern text NOT NULL, reading text, romaji text NOT NULL, level smallint NOT NULL,
    meaning text NOT NULL, formation text NOT NULL, examples jsonb NOT NULL, tags jsonb NOT NULL, notes text);
CREATE TABLE pos (code text NOT NULL, description text NOT NULL);
CREATE TABLE supplement_word (
    id text NOT NULL, word text NOT NULL, reading text NOT NULL, jmdict_id integer NOT NULL, meanings text NOT NULL);
CREATE TABLE sentence (
    sentence_id integer NOT NULL, ja text NOT NULL, furigana text, en text, tatoeba_id integer,
    content_words smallint NOT NULL);
CREATE TABLE sentence_word (sentence_id integer NOT NULL, word_id text NOT NULL);
CREATE TABLE meta (
    openjlpt_commit text NOT NULL, sqlite_sha256 text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
    sentences_total integer, content_tokens integer, content_tokens_mapped integer);
"""

KEYS_SQL = """
ALTER TABLE vocab ADD PRIMARY KEY (id);
ALTER TABLE vocab_example ADD PRIMARY KEY (vocab_id, ord);
ALTER TABLE vocab_example ADD FOREIGN KEY (vocab_id) REFERENCES vocab;
ALTER TABLE kanji ADD PRIMARY KEY (character);
ALTER TABLE grammar ADD PRIMARY KEY (id);
ALTER TABLE pos ADD PRIMARY KEY (code);
ALTER TABLE supplement_word ADD PRIMARY KEY (id);
ALTER TABLE sentence ADD PRIMARY KEY (sentence_id);
ALTER TABLE sentence_word ADD PRIMARY KEY (sentence_id, word_id);
CREATE INDEX ON vocab (word);
CREATE INDEX ON vocab (reading);
CREATE INDEX ON vocab (jmdict_id);
CREATE INDEX ON vocab (level);
CREATE INDEX ON kanji (level);
CREATE INDEX ON grammar (level);
CREATE INDEX ON sentence_word (word_id);
CREATE INDEX ON sentence (content_words);
"""

# ADR-010's precomputed recommender tables, from spike 2 (precompute.sql, rewritten).
DERIVED_SQL = """
CREATE TABLE word_kanji AS
SELECT DISTINCT v.id, letter AS kanji
FROM vocab v, regexp_split_to_table(v.word, '') AS letter
WHERE EXISTS (SELECT 1 FROM kanji k WHERE k.character = letter);
ALTER TABLE word_kanji ADD PRIMARY KEY (id, kanji);
CREATE INDEX ON word_kanji (kanji);

CREATE TABLE word_level AS
SELECT v.id, v.word, v.reading, v.level,
       coalesce((SELECT max(coalesce(k.freq, 9999)) FROM word_kanji wk  -- no rank: the rarest
                 JOIN kanji k ON k.character = wk.kanji WHERE wk.id = v.id), 0)::smallint AS commonness
FROM vocab v;
ALTER TABLE word_level ADD PRIMARY KEY (id);

CREATE TABLE kanji_leverage AS
SELECT wk.kanji, levels.level::smallint AS level,
       count(*) FILTER (WHERE w.level >= levels.level)::integer AS words
FROM word_kanji wk JOIN word_level w USING (id) CROSS JOIN generate_series(1, 5) AS levels(level)
GROUP BY wk.kanji, levels.level;
ALTER TABLE kanji_leverage ADD PRIMARY KEY (kanji, level);
"""

# What each table is, for a model reading the schema through MCP-backbone (D4). Changing
# these is a tool-level change (Phase 1, F2), so they're versioned here, with the code.
TABLE_COMMENTS = {
    "vocab": "JLPT words from OpenJLPT. level: 5 = N5 (easiest) ... 1 = N1. meanings are English glosses.",
    "vocab_example": "Example sentences per word (from Tatoeba, CC BY 2.0 FR); furigana as {kanji|reading}.",
    "kanji": "JLPT kanji with readings, meanings, strokes and KANJIDIC2 frequency (freq: 1 = most frequent).",
    "grammar": "OpenJLPT's grammar points, N5-N1, with meaning, formation and examples.",
    "pos": "Part-of-speech codes used in vocab.pos (JMdict's).",
    "supplement_word": "Juku's reviewed supplement: common words in no JLPT list; they have no level.",
    "sentence": "Example sentences in which every content word maps to one word (reading practice).",
    "sentence_word": "Which words each reading-practice sentence contains.",
    "word_kanji": "The kanji in each word's spelling.",
    "word_level": "Each word's level and commonness (its rarest kanji's frequency rank; 0 = kana only).",
    "kanji_leverage": "How many words at or easier than `level` contain the kanji.",
    "meta": "Which OpenJLPT build this is, when it was loaded, and how much of the reading index mapped.",
    "words_overview": "One row per word: spelling, reading, level as N5..N1, English meanings joined by '; '.",
    "grammar_overview": "One row per grammar point, with its level as N5..N1.",
}

VIEWS_SQL = """
CREATE VIEW words_overview AS
SELECT v.id, v.word, v.reading, 'N' || v.level AS jlpt_level,
       (SELECT string_agg(meaning, '; ') FROM jsonb_array_elements_text(v.meanings) AS meaning) AS meanings,
       v.jmdict_id
FROM vocab v;
CREATE VIEW grammar_overview AS
SELECT g.id, g.pattern, g.reading, 'N' || g.level AS jlpt_level, g.meaning, g.formation
FROM grammar g;
"""


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
        await _load_reading_index(connection, index)
        await connection.execute(
            text(
                "INSERT INTO meta (openjlpt_commit, sqlite_sha256, sentences_total, content_tokens, "
                "content_tokens_mapped) VALUES (:commit, :sha, :sentences, :tokens, :mapped)"
            ),
            {
                "commit": commit,
                "sha": source.sqlite_sha256,
                "sentences": index.sentences_total if with_reading_index else None,
                "tokens": index.content_tokens if with_reading_index else None,
                "mapped": index.content_tokens_mapped if with_reading_index else None,
            },
        )
        await _execute_script(connection, KEYS_SQL)
        await _execute_script(connection, DERIVED_SQL)
        await _execute_script(connection, VIEWS_SQL)
        for table, comment in TABLE_COMMENTS.items():
            kind = "VIEW" if table.endswith("_overview") else "TABLE"
            await connection.execute(text(f"COMMENT ON {kind} {table} IS '{comment.replace("'", "''")}'"))
        await connection.execute(text("ANALYZE"))
        row_counts = rows.counts()
        table_md5 = {table: await _table_md5(connection, table) for table in row_counts}
        disappeared = await _disappeared_ids(connection)
        await connection.execute(text(f"DROP SCHEMA IF EXISTS {LIVE_SCHEMA} CASCADE"))
        await connection.execute(text(f"ALTER SCHEMA {STAGING_SCHEMA} RENAME TO {LIVE_SCHEMA}"))
        await connection.execute(text(f"GRANT USAGE ON SCHEMA {LIVE_SCHEMA} TO {READER_ROLE}"))
        await connection.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA {LIVE_SCHEMA} TO {READER_ROLE}"))
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
