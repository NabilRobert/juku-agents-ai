"""Loading the pinned OpenJLPT build (slice 1): checksums, exact rows, derived tables, the reading index.

Standard checks, "loading the dictionary": checksums match the recorded
ones; row counts match the release's; a load into a fresh database gives
identical rows (here, spike 1's md5 of every table).
"""

import asyncio
import shutil
from pathlib import Path

import pytest
from juku_data.dictionary.load import LoadReport, load_dictionary
from juku_data.dictionary.pin import EXPECTED_ROW_COUNTS, EXPECTED_TABLE_MD5, OPENJLPT_COMMIT
from juku_data.dictionary.source import DictionaryError, sha256_of, verify_source
from juku_testkit.databases import TestDatabase, create_database, drop_database, require_openjlpt
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def test_a_changed_file_is_refused_before_anything_is_loaded(tmp_path: Path) -> None:
    folder = require_openjlpt()
    for name in ("openjlpt.sqlite", "NOTICE.md"):
        shutil.copy(folder / name, tmp_path / name)
    with (tmp_path / "openjlpt.sqlite").open("ab") as file:
        file.write(b"\0")
    with pytest.raises(DictionaryError, match=r"SHA-256 .* not the pinned"):
        verify_source(tmp_path)


def test_a_missing_file_says_how_to_fetch_it(tmp_path: Path) -> None:
    with pytest.raises(DictionaryError, match="juku-data fetch-dictionary"):
        verify_source(tmp_path)


async def scalar(engine: AsyncEngine, sql: str) -> object:
    async with engine.connect() as connection:
        return await connection.scalar(text(sql))


async def table_md5(engine: AsyncEngine, table: str) -> str:
    """Spike 1's hash: md5 of every row's text, in order."""
    value = await scalar(engine, f"SELECT md5(string_agg(t::text, E'\\n' ORDER BY t::text)) FROM ojlpt.{table} t")
    return str(value)


@pytest.mark.parametrize(("table", "count"), sorted(EXPECTED_ROW_COUNTS.items()))
async def test_the_load_has_the_builds_row_counts(dict_engine: AsyncEngine, table: str, count: int) -> None:
    assert await scalar(dict_engine, f"SELECT count(*) FROM ojlpt.{table}") == count


@pytest.mark.parametrize(("table", "md5"), sorted(EXPECTED_TABLE_MD5.items()))
async def test_the_load_reproduces_spike_1_row_for_row(dict_engine: AsyncEngine, table: str, md5: str) -> None:
    assert await table_md5(dict_engine, table) == md5


async def test_the_load_records_its_version(dict_engine: AsyncEngine) -> None:
    assert await scalar(dict_engine, "SELECT openjlpt_commit FROM ojlpt.meta") == OPENJLPT_COMMIT
    sqlite_sha256 = sha256_of(require_openjlpt() / "openjlpt.sqlite")
    assert await scalar(dict_engine, "SELECT sqlite_sha256 FROM ojlpt.meta") == sqlite_sha256


async def word_id(engine: AsyncEngine, word: str) -> str:
    async with engine.connect() as connection:
        found = await connection.scalar(text("SELECT id FROM ojlpt.vocab WHERE word = :word"), {"word": word})
    assert isinstance(found, str), word
    return found


async def test_each_word_lists_the_kanji_in_its_spelling(dict_engine: AsyncEngine) -> None:
    async with dict_engine.connect() as connection:
        kanji = await connection.scalars(
            text("SELECT kanji FROM ojlpt.word_kanji WHERE id = :id ORDER BY kanji"),
            {"id": await word_id(dict_engine, "一つ")},
        )
        assert list(kanji) == ["一"]


async def test_a_kana_only_word_counts_as_common(dict_engine: AsyncEngine) -> None:
    async with dict_engine.connect() as connection:
        commonness = await connection.scalar(
            text("SELECT commonness FROM ojlpt.word_level WHERE id = :id"), {"id": await word_id(dict_engine, "ここ")}
        )
    assert commonness == 0


async def test_a_words_commonness_is_its_rarest_kanjis_frequency_rank(dict_engine: AsyncEngine) -> None:
    async with dict_engine.connect() as connection:
        expected = await connection.scalar(
            text(
                "SELECT max(coalesce(k.freq, 9999)) FROM ojlpt.word_kanji wk "
                "JOIN ojlpt.kanji k ON k.character = wk.kanji WHERE wk.id = :id"
            ),
            {"id": await word_id(dict_engine, "昨日")},
        )
        actual = await connection.scalar(
            text("SELECT commonness FROM ojlpt.word_level WHERE id = :id"), {"id": await word_id(dict_engine, "昨日")}
        )
    assert actual == expected


async def test_leverage_counts_the_words_at_or_below_a_level_with_the_kanji(dict_engine: AsyncEngine) -> None:
    n5_words_with_day = await scalar(
        dict_engine,
        "SELECT count(*) FROM ojlpt.word_kanji wk JOIN ojlpt.vocab v USING (id) WHERE wk.kanji = '日' AND v.level = 5",
    )
    leverage = await scalar(dict_engine, "SELECT words FROM ojlpt.kanji_leverage WHERE kanji = '日' AND level = 5")
    assert leverage == n5_words_with_day
    assert isinstance(leverage, int) and leverage > 0


async def test_the_supplement_words_are_loaded_with_no_level(dict_engine: AsyncEngine) -> None:
    async with dict_engine.connect() as connection:
        rows = (await connection.execute(text("SELECT word, jmdict_id FROM ojlpt.supplement_word ORDER BY id"))).all()
    assert ("父", 1497610) in [tuple(row) for row in rows]
    assert await scalar(dict_engine, "SELECT count(*) FROM ojlpt.word_level WHERE id LIKE 'sup-%'") == 0


async def sentence_words(engine: AsyncEngine, ja: str) -> set[str]:
    async with engine.connect() as connection:
        found = await connection.scalars(
            text(
                "SELECT sw.word_id FROM ojlpt.sentence s JOIN ojlpt.sentence_word sw USING (sentence_id) "
                "WHERE s.ja = :ja"
            ),
            {"ja": ja},
        )
        return set(found)


async def test_a_sentence_maps_each_content_word_to_one_word_id(dict_engine: AsyncEngine) -> None:
    expected = {await word_id(dict_engine, word) for word in ("信号", "青", "変わる")}
    assert await sentence_words(dict_engine, "信号が青に変わったわよ。") == expected


async def test_a_supplement_word_maps_in_a_sentence(dict_engine: AsyncEngine) -> None:
    async with dict_engine.connect() as connection:
        mapped = await connection.scalar(text("SELECT count(*) FROM ojlpt.sentence_word WHERE word_id = 'sup-1497610'"))
    assert isinstance(mapped, int) and mapped > 0


async def test_reading_practice_maps_about_as_much_as_spike_4_measured(dict_engine: AsyncEngine) -> None:
    """Spike 4: 90.7% of content tokens map to one word; 63-66% of sentences map completely."""
    tokens, mapped = (
        await scalar(dict_engine, "SELECT content_tokens FROM ojlpt.meta"),
        await scalar(dict_engine, "SELECT content_tokens_mapped FROM ojlpt.meta"),
    )
    sentences_total = await scalar(dict_engine, "SELECT sentences_total FROM ojlpt.meta")
    sentences_mapped = await scalar(dict_engine, "SELECT count(*) FROM ojlpt.sentence")
    assert isinstance(tokens, int) and isinstance(mapped, int)
    assert isinstance(sentences_total, int) and isinstance(sentences_mapped, int)
    assert mapped / tokens >= 0.90
    assert sentences_mapped / sentences_total >= 0.63


async def test_the_reader_role_can_read_but_not_write(dict_engine: AsyncEngine) -> None:
    async with dict_engine.connect() as connection:
        await connection.execute(text("SET ROLE dict_reader"))
        assert await connection.scalar(text("SELECT count(*) FROM ojlpt.grammar")) == 526
        with pytest.raises(DBAPIError, match=r"permission denied|read-only"):
            await connection.execute(text("DELETE FROM ojlpt.pos"))
        await connection.rollback()


async def test_the_model_facing_views_have_comments(dict_engine: AsyncEngine) -> None:
    missing = await scalar(
        dict_engine,
        "SELECT string_agg(c.relname, ', ') FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'ojlpt' AND c.relkind IN ('r', 'v') AND obj_description(c.oid, 'pg_class') IS NULL",
    )
    assert missing is None


async def test_a_reload_without_a_word_reports_the_word_as_disappeared(tmp_path: Path) -> None:
    """The update policy: OpenJLPT's IDs are stable, and an ID that vanishes is reported, not ignored."""
    import sqlite3

    folder = require_openjlpt()
    for name in ("openjlpt.sqlite", "NOTICE.md"):
        shutil.copy(folder / name, tmp_path / name)
    database: TestDatabase = await asyncio.to_thread(create_database, "juku_test_reload")
    engine = create_async_engine(database.sqlalchemy_url)
    try:
        first = await load_dictionary(engine, verify_source(folder), with_reading_index=False)
        assert first.disappeared_ids == []
        with sqlite3.connect(tmp_path / "openjlpt.sqlite") as connection:
            connection.execute("DELETE FROM vocab WHERE word = '一つ'")
        changed = verify_source(tmp_path, expected_sqlite_sha256=sha256_of(tmp_path / "openjlpt.sqlite"))
        second: LoadReport = await load_dictionary(engine, changed, with_reading_index=False)
        assert second.disappeared_ids == ["537f8af3d6"]
        assert second.row_counts["vocab"] == EXPECTED_ROW_COUNTS["vocab"] - 1
    finally:
        await engine.dispose()
        await asyncio.to_thread(drop_database, database)
