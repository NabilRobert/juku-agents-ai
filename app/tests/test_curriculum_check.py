"""Keiko's weekly curriculum check (curriculum_check.py, pipeline/facts.py and run.py): queued, run, shown."""

from datetime import timedelta

from juku_app.curriculum_check import is_check_queued, latest_note, queue_check_if_due
from juku_app.pipeline.facts import curriculum_facts
from juku_app.pipeline.run import due_learners, run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_data.engine.curriculum_models import CurriculumLevel, CurriculumOverview, UnitStatus
from pipeline_helpers import crew_of, fixture_learner, services_for, sunday_evening


def unit(unit_id: int, status: str) -> UnitStatus:
    return UnitStatus.model_validate(
        {
            "unit_id": unit_id,
            "level": 5,
            "number": unit_id,
            "words_total": 15,
            "words_known": 0,
            "grammar_total": 1,
            "grammar_studied": 0,
            "sentences_total": 0,
            "sentences_read": 0,
            "status": status,
        }
    )


def overview(done: int, total: int) -> CurriculumOverview:
    units = [
        unit(number, "done" if number <= done else "current" if number == done + 1 else "later")
        for number in range(1, total + 1)
    ]
    current = done + 1 if done < total else None
    return CurriculumOverview(
        target_level=5,
        units_total=total,
        units_done=done,
        current_unit_id=current,
        levels=[CurriculumLevel(level=5, units=units)],
    )


def test_keiko_is_told_the_units_a_week_the_exam_needs_rounded_up() -> None:
    facts = curriculum_facts(overview(done=5, total=45), weeks_left=6)
    assert facts.units_per_week_needed == 7  # 40 units in 6 weeks
    assert facts.current_unit is not None and facts.current_unit.unit_id == 6
    assert [(level.level, level.units_done, level.units_total) for level in facts.levels] == [(5, 5, 45)]


def test_without_an_exam_date_there_is_no_pace_to_need() -> None:
    assert curriculum_facts(overview(done=5, total=45), weeks_left=None).units_per_week_needed is None
    assert curriculum_facts(overview(done=45, total=45), weeks_left=0).current_unit is None


async def test_a_visit_after_a_week_without_a_run_queues_a_check_that_any_day_runs(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)
    wednesday = sunday_evening(learner.timezone) - timedelta(days=4)
    assert learner.id not in {due.id for due in await due_learners(engine_databases, rules, wednesday)}
    await queue_check_if_due(engine_databases.app, learner.id, wednesday)
    assert await is_check_queued(engine_databases.app, learner.id)
    assert learner.id in {due.id for due in await due_learners(engine_databases, rules, wednesday)}


async def test_the_run_saves_keikos_note_and_answers_the_check(engine_databases: Databases, rules: Rules) -> None:
    learner = await fixture_learner(engine_databases, rules)
    wednesday = sunday_evening(learner.timezone) - timedelta(days=4)
    await queue_check_if_due(engine_databases.app, learner.id, wednesday)
    outcome = await run_weekly(services_for(engine_databases, rules, crew_of()), learner, wednesday)
    note = await latest_note(engine_databases.app, learner.id)
    assert outcome.status == "published"
    assert note is not None and "[ref:curriculum]" in note.body
    assert not await is_check_queued(engine_databases.app, learner.id)


async def test_a_visit_within_a_week_of_a_run_queues_nothing(engine_databases: Databases, rules: Rules) -> None:
    learner = await fixture_learner(engine_databases, rules)
    sunday = sunday_evening(learner.timezone)
    await run_weekly(services_for(engine_databases, rules, crew_of()), learner, sunday)
    await queue_check_if_due(engine_databases.app, learner.id, sunday + timedelta(days=6))
    assert not await is_check_queued(engine_databases.app, learner.id)
    await queue_check_if_due(engine_databases.app, learner.id, sunday + timedelta(days=8))
    assert await is_check_queued(engine_databases.app, learner.id)
