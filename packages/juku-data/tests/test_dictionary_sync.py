"""The dictionary's index, mirrored into the app database, and the fetch's checksum guard."""

from pathlib import Path

import httpx
import pytest
from juku_data.dictionary.fetch import fetch_dictionary
from juku_data.dictionary.pin import OPENJLPT_COMMIT
from juku_data.dictionary.source import DictionaryError
from juku_data.dictionary.sync import sync_index
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def count(engine: AsyncEngine, sql: str) -> object:
    async with engine.connect() as connection:
        return await connection.scalar(text(sql))


async def test_the_mirror_holds_every_word_kanji_and_leverage_row(
    dict_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    report = await sync_index(dict_engine, app_engine)
    assert report.words == await count(dict_engine, "SELECT count(*) FROM ojlpt.word_level") == 7811
    assert await count(app_engine, "SELECT count(*) FROM learning.dictionary_words") == report.words
    assert await count(app_engine, "SELECT count(*) FROM learning.dictionary_word_kanji") == report.word_kanji
    assert await count(app_engine, "SELECT count(*) FROM learning.dictionary_kanji") == report.kanji == 2383
    assert await count(app_engine, "SELECT count(*) FROM learning.kanji_leverage") == report.leverage_rows
    assert await count(app_engine, "SELECT openjlpt_commit FROM learning.dictionary_version") == OPENJLPT_COMMIT


async def test_a_learner_item_missing_from_the_dictionary_is_reported(
    dict_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    async with app_engine.begin() as connection:
        learner_id = await connection.scalar(
            text(
                "INSERT INTO learning.learners (public_id, nickname, target_level) "
                "VALUES ('lrn-gone', 'x', 5) RETURNING id"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO learning.learner_state (learner_id, item_id, last_seen_at) "
                "VALUES (:id, 'gone-word', now())"
            ),
            {"id": learner_id},
        )
    try:
        report = await sync_index(dict_engine, app_engine)
        assert report.items_missing_from_dictionary == ["gone-word"]
    finally:
        async with app_engine.begin() as connection:
            await connection.execute(text("DELETE FROM learning.learners WHERE public_id = 'lrn-gone'"))


def serve(body: bytes) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=body)))


async def test_a_download_that_does_not_match_its_pin_is_deleted(tmp_path: Path) -> None:
    with pytest.raises(DictionaryError, match="didn't match its pinned SHA-256"):
        await fetch_dictionary(tmp_path, serve(b"not the dictionary"))
    assert list(tmp_path.iterdir()) == []


async def test_a_failed_download_says_what_answered(tmp_path: Path) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(404)))
    with pytest.raises(DictionaryError, match="answered 404"):
        await fetch_dictionary(tmp_path, client)


async def test_after_a_sync_every_learner_is_rebuilt_against_the_new_mirror(
    engine_databases: object, dict_engine: AsyncEngine, app_engine: AsyncEngine
) -> None:
    from juku_data.engine import Databases, verify_state
    from juku_data.engine.recompute import rebuild_everyone

    assert isinstance(engine_databases, Databases)
    await sync_index(dict_engine, app_engine)
    rebuilt = await rebuild_everyone(app_engine, batch_size=7)
    assert rebuilt == await count(app_engine, "SELECT count(*) FROM learning.learners")
    assert await verify_state(engine_databases) == []
