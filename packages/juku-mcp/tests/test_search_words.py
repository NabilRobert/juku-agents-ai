"""JI2: search_words finds a word by kanji, kana, romaji or English; its input is normalized first (JI1)."""

import pytest
from juku_common.delegation import Signer
from mcp import Client
from mcp_helpers import Learners, call, token_for

EAT = "86f67e2dc3"  # 食べる/たべる in OpenJLPT


@pytest.mark.parametrize("query", ["食べる", "たべる", "taberu", "ＴＡＢＥＲＵ", "to eat", "  食べる "])
async def test_each_way_of_typing_finds_the_word(
    client: Client, signer: Signer, learners: Learners, query: str
) -> None:
    answer = await call(client, "search_words", token_for(signer, learners.a), {"query": query})
    assert not answer.is_error, answer.text
    assert EAT in [word["word_id"] for word in answer.body["words"]][:5]


async def test_at_most_ten_words_come_back(client: Client, signer: Signer, learners: Learners) -> None:
    answer = await call(client, "search_words", token_for(signer, learners.a), {"query": "to"})
    assert 0 < len(answer.body["words"]) <= 10


@pytest.mark.parametrize("query", ["", "   ", "x" * 65])
async def test_an_empty_or_overlong_query_is_refused(
    client: Client, signer: Signer, learners: Learners, query: str
) -> None:
    answer = await call(client, "search_words", token_for(signer, learners.a), {"query": query})
    assert (answer.is_error, answer.body["refused"]) == (True, "bad_arguments")


async def test_get_memory_answers_until_memory_lands_in_slice_4(
    client: Client, signer: Signer, learners: Learners
) -> None:
    answer = await call(client, "get_memory", token_for(signer, learners.a))
    assert (answer.is_error, answer.body["notes"]) == (False, [])
