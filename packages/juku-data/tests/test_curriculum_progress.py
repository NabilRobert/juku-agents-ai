"""The curriculum for one learner (engine/curriculum.py, placement.py): progress, today's lesson, placement."""

from datetime import UTC, date, datetime

import pytest
from juku_data.engine import (
    Databases,
    PlacementAnswer,
    UnknownGrammarError,
    create_learner,
    get_curriculum,
    get_placement_questions,
    get_today,
    get_unit,
    mark_grammar_studied,
    mark_known,
    place_learner,
    record_sentence_read,
    verify_state,
)
from juku_data.engine.curriculum import words_a_day
from juku_data.engine.placement import placed_through, sampled_units
from juku_data.engine.quiz import correct_option

NOW = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)
TODAY = date(2026, 11, 5)


async def finish_unit(db: Databases, learner_id: int, unit_id: int) -> None:
    unit = await get_unit(db, learner_id, unit_id)
    assert unit is not None
    for word in unit.words:
        await mark_known(db, learner_id, word.word_id, NOW)
    for point in unit.grammar:
        await mark_grammar_studied(db, learner_id, point.grammar_id, NOW)
    for sentence in unit.sentences:
        await record_sentence_read(db, learner_id, sentence.sentence_id, NOW)


def test_the_days_words_follow_the_plans_pace_within_bounds() -> None:
    assert [words_a_day(pace) for pace in (None, 7, 70, 500, 1)] == [10, 3, 10, 30, 3]


def test_placement_samples_units_spread_through_the_level() -> None:
    assert sampled_units(list(range(1, 46)), 15)[:3] == [1, 4, 7] and sampled_units(list(range(1, 46)), 15)[-1] == 45
    assert sampled_units([1, 2, 3], 15) == [1, 2, 3]


def test_one_slip_is_forgiven_and_the_second_wrong_answer_ends_the_placement() -> None:
    units = list(range(1, 11))
    assert placed_through([(1, True), (3, False), (5, True), (7, True)], units) == 10
    assert placed_through([(1, True), (3, False), (5, True), (7, False), (9, True)], units) == 5
    assert placed_through([(1, False), (3, False)], units) == 0


async def test_a_new_learner_starts_at_n5_unit_one(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="kur-a", target_level=2)
    overview = await get_curriculum(engine_databases, learner.id)
    assert overview.current_unit_id == 1 and overview.units_done == 0
    assert [level.level for level in overview.levels] == [5, 4, 3, 2]
    assert overview.units_total == sum(len(level.units) for level in overview.levels) == 317


async def test_a_learner_aiming_at_n4_has_a_shorter_path(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="kur-b", target_level=4)
    overview = await get_curriculum(engine_databases, learner.id)
    assert [level.level for level in overview.levels] == [5, 4]


async def test_finishing_a_unit_moves_the_learner_to_the_next(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="kur-c", target_level=5)
    await finish_unit(engine_databases, learner.id, 1)
    overview = await get_curriculum(engine_databases, learner.id)
    assert overview.current_unit_id == 2 and overview.units_done == 1
    assert await verify_state(engine_databases, [learner.id]) == []  # FF3, with learner_studied


async def test_todays_lesson_is_the_current_units_next_words_and_grammar(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="kur-d", target_level=5)
    plan = await get_today(engine_databases, learner.id, TODAY, NOW)
    unit = await get_unit(engine_databases, learner.id, 1)
    assert plan.unit is not None and plan.unit.unit_id == 1 and unit is not None
    assert plan.words_target == 10 and [word.word_id for word in plan.new_words] == [w.word_id for w in unit.words][:10]
    assert plan.grammar is not None and plan.grammar.grammar_id == unit.grammar[0].grammar_id
    await mark_known(engine_databases, learner.id, plan.new_words[0].word_id, NOW)
    after = await get_today(engine_databases, learner.id, TODAY, NOW)
    assert after.words_done == 1 and len(after.new_words) == 9


async def test_an_unknown_grammar_point_is_refused(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="kur-e", target_level=5)
    with pytest.raises(UnknownGrammarError):
        await mark_grammar_studied(engine_databases, learner.id, "no-such-point", NOW)


async def test_placing_through_n5_marks_its_units_done_and_its_words_known(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="kur-f", target_level=2)
    questions = await get_placement_questions(engine_databases, learner.id, 5)
    answers = []
    for item in questions.items:
        right = await correct_option(engine_databases.dictionary, item.word_id, item.kind)
        assert right is not None
        answers.append(PlacementAnswer(word_id=item.word_id, kind=item.kind, chosen=right))
    result = await place_learner(engine_databases, learner.id, 5, answers, NOW)
    overview = await get_curriculum(engine_databases, learner.id)
    assert result.passed_level and result.correct == result.total == len(questions.items) == 15
    assert overview.units_done == 45 and overview.current_unit_id == 46
    assert await verify_state(engine_databases, [learner.id]) == []
