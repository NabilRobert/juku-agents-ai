"""The engine's write side: learners, levels, timezones, and refusing what isn't there."""

from datetime import UTC, datetime

import pytest
from fixture_learners import known_words, load_fixture, replay
from juku_data.engine import (
    Databases,
    LearnerNotFoundError,
    UnknownWordError,
    create_learner,
    get_learner,
    get_progress,
    mark_known,
    recommend_words,
    set_target_level,
    set_timezone,
    verify_state,
)
from oracle import load_oracle_dictionary, recommend

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the engine lands in the next commits")

PUBLIC_ID_LENGTH = 16


async def test_a_new_learner_gets_a_random_url_safe_public_id(engine_databases: Databases) -> None:
    first = await create_learner(engine_databases, nickname="a", target_level=5)
    second = await create_learner(engine_databases, nickname="b", target_level=5)
    assert first.public_id != second.public_id
    assert len(first.public_id) == PUBLIC_ID_LENGTH
    assert first.public_id.replace("-", "").replace("_", "").isalnum()
    assert (await get_learner(engine_databases, first.public_id)).id == first.id


async def test_an_unknown_public_id_is_an_error(engine_databases: Databases) -> None:
    with pytest.raises(LearnerNotFoundError):
        await get_learner(engine_databases, "nobody")


async def test_marking_a_word_that_is_not_in_the_dictionary_is_refused(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="c", target_level=5)
    with pytest.raises(UnknownWordError):
        await mark_known(engine_databases, learner.id, "no-such-word", datetime.now(UTC))
    assert (await get_progress(engine_databases, learner.id)).known_words == 0


async def test_a_level_outside_n5_to_n2_is_refused(engine_databases: Databases) -> None:
    with pytest.raises(ValueError, match="N5 to N2"):
        await create_learner(engine_databases, nickname="d", target_level=1)


async def test_an_unknown_timezone_is_refused(engine_databases: Databases) -> None:
    with pytest.raises(ValueError, match="timezone"):
        await create_learner(engine_databases, nickname="e", target_level=5, timezone="Mars/Olympus")


async def test_changing_level_recomputes_the_recommendations(engine_databases: Databases) -> None:
    fixture = await load_fixture(engine_databases.dictionary, "eka")
    learner = await replay(engine_databases, fixture, suffix="-level")
    await set_target_level(engine_databases, learner.id, 4)
    oracle = recommend(await load_oracle_dictionary(engine_databases.dictionary), known_words(fixture), 4)
    words = (await recommend_words(engine_databases, learner.id)).words
    assert [word.word_id for word in words] == [word["word_id"] for word in oracle]
    assert await verify_state(engine_databases, [learner.id]) == []


async def test_changing_timezone_recounts_days_in_the_new_zone(engine_databases: Databases) -> None:
    fixture = await load_fixture(engine_databases.dictionary, "citra")
    learner = await replay(engine_databases, fixture, suffix="-zone")
    await set_timezone(engine_databases, learner.id, "Asia/Jakarta")
    assert await verify_state(engine_databases, [learner.id]) == []
    # In WIB, 学校's answers (23:30 and 00:30 WITA) fall on one day, so it is no longer known.
    assert (await get_progress(engine_databases, learner.id)).known_words == 150
