"""Studying words in context (routes/study.py): a word's page, the grammar pages, and a kanji's details."""

from collections.abc import AsyncIterator

import httpx
import pytest
from juku_app.invites import issue_codes
from juku_data.engine import Databases
from sqlalchemy import text
from web_helpers import client_for, csrf_of, deps, page_props, sign_up


@pytest.fixture
async def learner(engine_databases: Databases) -> AsyncIterator[httpx.AsyncClient]:
    """A signed-in N4 learner."""
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, level="4")
        yield client


async def taberu(db: Databases) -> str:
    async with db.dictionary.connect() as connection:
        found = await connection.scalar(text("SELECT id FROM ojlpt.vocab WHERE word = '食べる' AND reading = 'たべる'"))
    assert isinstance(found, str)
    return found


async def test_a_words_page_shows_it_in_use_with_each_example_explained(
    engine_databases: Databases, learner: httpx.AsyncClient
) -> None:
    page = await learner.get(f"/kata/{await taberu(engine_databases)}")
    assert page.status_code == 200
    shown = page_props(page)
    assert "to eat" in shown["entry"]["meanings"]
    assert shown["entry"]["examples"]
    assert all(example["ja"] in shown["breakdowns"] for example in shown["entry"]["examples"])


async def test_a_word_that_doesnt_exist_has_no_page(learner: httpx.AsyncClient) -> None:
    assert (await learner.get("/kata/no-such-word")).status_code == 404


async def test_marking_a_word_known_from_its_page_returns_to_it(
    engine_databases: Databases, learner: httpx.AsyncClient
) -> None:
    word_id = await taberu(engine_databases)
    page = await learner.get(f"/kata/{word_id}")
    marked = await learner.post(f"/kata/{word_id}/dikuasai", data={"csrf": csrf_of(page), "back_to": "word"})
    assert marked.status_code == 303 and marked.headers["location"] == f"/kata/{word_id}"
    assert page_props(await learner.get(f"/kata/{word_id}"))["entry"]["is_known"] is True


async def test_the_grammar_page_opens_at_the_learners_level(learner: httpx.AsyncClient) -> None:
    shown = page_props(await learner.get("/tata-bahasa"))
    assert shown["level"] == 4 and {point["level"] for point in shown["points"]} == {4}
    assert page_props(await learner.get("/tata-bahasa?level=5"))["points"][0]["pattern"] == "〜は"
    assert page_props(await learner.get("/tata-bahasa?level=1"))["level"] == 4  # N1 isn't one of Juku's levels


async def test_a_grammar_point_explains_how_its_formed_with_its_examples(learner: httpx.AsyncClient) -> None:
    shown = page_props(await learner.get("/tata-bahasa/wa"))
    assert shown["point"]["formation"] == "Noun + は"
    assert len(shown["breakdowns"]) == len(shown["point"]["examples"]) == 3
    assert (await learner.get("/tata-bahasa/no-such-point")).status_code == 404


async def test_a_kanjis_readings_come_as_json(learner: httpx.AsyncClient) -> None:
    kanji = await learner.get("/kanji/生")
    assert kanji.status_code == 200 and "セイ" in kanji.json()["onyomi"]
    assert (await learner.get("/kanji/あ")).status_code == 404
    assert (await learner.get("/kanji/生活")).status_code == 404  # one character at a time


async def test_the_study_pages_need_sign_in(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as stranger:
        for path in ("/kata/x", "/tata-bahasa", "/tata-bahasa/wa", "/kanji/生"):
            assert (await stranger.get(path)).status_code in {303, 307}, path
