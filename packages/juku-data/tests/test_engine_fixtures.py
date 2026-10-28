"""E1: each fixture learner's exact outputs (progress, recommendations, reading, plan, mistakes, activity).

The recommendations and reading sentences are compared with
tests/fixtures/expected/*.json, which the oracle wrote from ADR-010 and
LE4's text before the engine existed. The rest is worked out by hand in
each test, from the fixture's events.
"""

import json
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fixture_learners import EXPECTED, FIXTURE_NAMES, FixtureLearner
from juku_data.engine import (
    Databases,
    find_reading_sentences,
    get_mistakes,
    get_plan,
    get_progress,
    get_recent_activity,
    recommend_words,
)
from juku_data.engine.models import Learner
from sqlalchemy import text

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the engine lands in the next commits")

Replayed = dict[str, tuple[FixtureLearner, Learner]]
WIB = ZoneInfo("Asia/Jakarta")


def expected(name: str) -> dict[str, Any]:
    return json.loads((EXPECTED / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", FIXTURE_NAMES)
async def test_recommendations_match_the_oracle_exactly(
    engine_databases: Databases, fixtures_and_learners: Replayed, name: str
) -> None:
    _, learner = fixtures_and_learners[name]
    words = (await recommend_words(engine_databases, learner.id)).words
    actual = [
        {"word_id": w.word_id, "word": w.word, "level": w.level, "new_kanji": w.new_kanji, "leverage": w.leverage}
        for w in words
    ]
    assert actual == expected(name)["recommendations"]


@pytest.mark.parametrize("name", FIXTURE_NAMES)
async def test_each_recommendation_states_its_reason_from_its_row(
    engine_databases: Databases, fixtures_and_learners: Replayed, name: str
) -> None:
    _, learner = fixtures_and_learners[name]
    for word in (await recommend_words(engine_databases, learner.id)).words:
        gap = f"Kata N{word.level} yang belum dikuasai. " if word.level > learner.target_level else ""
        new = (
            f"1 kanji baru: {word.new_kanji}, muncul di {word.leverage} kata N{learner.target_level}."
            if word.new_kanji
            else "Tanpa kanji baru."
        )
        assert word.reason == gap + new
        assert word.meanings, word.word


@pytest.mark.parametrize("name", FIXTURE_NAMES)
async def test_reading_sentences_match_the_oracle_exactly(
    engine_databases: Databases, fixtures_and_learners: Replayed, name: str
) -> None:
    _, learner = fixtures_and_learners[name]
    sentences = (await find_reading_sentences(engine_databases, learner.id)).sentences
    actual = [{"sentence_id": s.sentence_id, "new_word_id": s.new_word_id} for s in sentences]
    assert actual == expected(name)["reading_sentences"]


@pytest.mark.parametrize("name", FIXTURE_NAMES)
async def test_known_words_match_le1_folded_by_hand(
    engine_databases: Databases, fixtures_and_learners: Replayed, name: str
) -> None:
    _, learner = fixtures_and_learners[name]
    assert (await get_progress(engine_databases, learner.id)).known_words == expected(name)["known_words"]


async def word_state(db: Databases, learner: Learner, word_id: str) -> tuple[bool, int, int | None]:
    async with db.app.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT is_known, correct_days, box FROM learning.learner_state "
                    "WHERE learner_id = :learner AND item_id = :item"
                ),
                {"learner": learner.id, "item": word_id},
            )
        ).one()
    return bool(row[0]), int(row[1]), row[2]


async def test_ayu_starts_with_nothing_and_a_plan_for_all_of_n5(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, ayu = fixtures_and_learners["ayu"]
    progress = await get_progress(engine_databases, ayu.id)
    assert progress.known_words == 0
    assert [(level.level, level.words_known, level.words_total) for level in progress.levels] == [
        (5, 0, 674),
        (4, 0, 630),
        (3, 0, 1659),
        (2, 0, 1778),
        (1, 0, 3070),
    ]
    plan = await get_plan(engine_databases, ayu.id, date(2026, 11, 1))
    # 80% of N5's 674 words is 539.2, so 540; 35 days to 6 December is 5 weeks; 540 / 5 = 108.
    assert (plan.words_in_scope, plan.words_needed, plan.weeks_left, plan.words_per_week) == (674, 540, 5, 108)
    assert (await get_mistakes(engine_databases, ayu.id, datetime(2026, 11, 8, tzinfo=WIB))).items == []


async def test_budi_two_days_make_a_word_known_and_one_day_does_not(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    fixture, budi = fixtures_and_learners["budi"]
    blue, rain = (event.word_id for event in fixture.events[60:63:2])
    assert blue and rain
    assert await word_state(engine_databases, budi, blue) == (True, 2, None)
    assert await word_state(engine_databases, budi, rain) == (False, 1, None)


async def test_budi_mistakes_are_due_in_box_order(engine_databases: Databases, fixtures_and_learners: Replayed) -> None:
    _, budi = fixtures_and_learners["budi"]
    mistakes = await get_mistakes(engine_databases, budi.id, datetime(2026, 11, 8, 12, 0, tzinfo=WIB))
    assert [(item.word, item.box, item.due_at.astimezone(WIB), item.is_due) for item in mistakes.items] == [
        ("川", 1, datetime(2026, 11, 7, 11, 0, tzinfo=WIB), True),
        ("山", 2, datetime(2026, 11, 8, 10, 0, tzinfo=WIB), True),
    ]
    earlier = await get_mistakes(engine_databases, budi.id, datetime(2026, 11, 7, 12, 0, tzinfo=WIB))
    assert [item.is_due for item in earlier.items] == [True, False]


async def test_budi_activity_is_counted_by_local_day(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, budi = fixtures_and_learners["budi"]
    activity = await get_recent_activity(engine_databases, budi.id, date(2026, 11, 8))
    by_day = {
        day.day: (day.quiz_answers, day.quiz_correct, day.words_marked, day.sentences_read) for day in activity.days
    }
    assert by_day == {
        date(2026, 11, 2): (0, 0, 60, 0),
        date(2026, 11, 3): (1, 1, 0, 0),
        date(2026, 11, 4): (1, 1, 0, 0),
        date(2026, 11, 5): (3, 2, 0, 0),
        date(2026, 11, 6): (2, 1, 0, 1),
    }


async def test_budi_without_an_exam_date_gets_no_weekly_pace(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, budi = fixtures_and_learners["budi"]
    plan = await get_plan(engine_databases, budi.id, date(2026, 11, 8))
    assert (plan.words_needed, plan.weeks_left, plan.words_per_week) == (540 - 61, None, None)


async def test_citra_the_learners_own_midnight_separates_days(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    fixture, citra = fixtures_and_learners["citra"]
    school, teacher = fixture.events[150].word_id, fixture.events[152].word_id
    assert school and teacher
    assert (await word_state(engine_databases, citra, school))[0] is True
    assert (await word_state(engine_databases, citra, teacher))[:2] == (False, 1)


async def test_citra_plans_for_n4_and_everything_easier(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, citra = fixtures_and_learners["citra"]
    plan = await get_plan(engine_databases, citra.id, date(2026, 11, 4))
    # N5 + N4 = 1,304 words; 80% is 1,043.2, so 1,044; minus 151 known = 893.
    # 32 days to the exam = 5 weeks; 893 / 5 = 178.6, so 179.
    assert (plan.words_in_scope, plan.words_needed, plan.weeks_left, plan.words_per_week) == (1304, 893, 5, 179)


async def test_dewi_an_unmarked_word_is_unknown_and_starts_its_days_again(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    fixture, dewi = fixtures_and_learners["dewi"]
    eat = fixture.events[0].word_id
    drink = fixture.events[1].word_id
    assert eat and drink
    assert (await word_state(engine_databases, dewi, eat))[0] is False
    assert await word_state(engine_databases, dewi, drink) == (True, 2, None)


async def test_eka_kanji_coverage_counts_the_kanji_in_known_words(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, eka = fixtures_and_learners["eka"]
    async with engine_databases.dictionary.connect() as connection:
        levels = dict(
            (
                await connection.execute(
                    text("SELECT character, level FROM ojlpt.kanji WHERE character = ANY(:kanji)"),
                    {"kanji": ["日", "曜", "一", "二", "今", "学", "生"]},
                )
            ).all()
        )
    expected_by_level = {level: sum(1 for value in levels.values() if value == level) for level in range(1, 6)}
    progress = await get_progress(engine_databases, eka.id)
    assert {level.level: level.kanji_known for level in progress.levels} == expected_by_level
    assert {level.level: level.words_known for level in progress.levels} == {5: 5, 4: 0, 3: 0, 2: 0, 1: 0}
