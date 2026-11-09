"""This week's strip on Home (engine/week.py): each day's lesson done against the day's target."""

from datetime import UTC, date, datetime

from juku_data.engine import Databases, create_learner, get_today, mark_grammar_studied, mark_known
from juku_data.engine.models import DayActivity
from juku_data.engine.week import _day_done

NOW = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)  # a Thursday
TODAY = date(2026, 11, 5)


def test_each_part_counts_only_up_to_its_own_target() -> None:
    busy_quiz_day = DayActivity(day=TODAY, quiz_answers=50, quiz_correct=40, words_marked=2, sentences_read=0)
    assert _day_done(busy_quiz_day, grammar=0, targets=(10, 10, 3, 1)) == 12
    assert _day_done(None, grammar=1, targets=(10, 10, 3, 1)) == 1


async def test_the_week_runs_monday_to_sunday_with_todays_work_on_today(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="week-a", target_level=5)
    plan = await get_today(engine_databases, learner.id, TODAY, NOW)
    assert plan.grammar is not None
    await mark_known(engine_databases, learner.id, plan.new_words[0].word_id, NOW)
    await mark_grammar_studied(engine_databases, learner.id, plan.grammar.grammar_id, NOW)
    week = (await get_today(engine_databases, learner.id, TODAY, NOW)).week
    assert [day.day.isoformat() for day in (week[0], week[-1])] == ["2026-11-02", "2026-11-08"]
    assert [day.done for day in week] == [0, 0, 0, 2, 0, 0, 0]
    assert week[3].target == plan.words_target + plan.quiz_target + plan.sentences_target + 1
    assert [day.is_future for day in week] == [False] * 4 + [True] * 3
