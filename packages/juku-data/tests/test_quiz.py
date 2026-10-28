"""LE2: quizzes generated and graded in code, with distractors from the same level and similar items."""

from datetime import UTC, date, datetime

import pytest
from fixture_learners import FixtureLearner
from juku_data.engine import Databases, grade_answer, make_quiz
from juku_data.engine.models import Learner, QuizItem
from sqlalchemy import text

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the engine lands in the next commits")

Replayed = dict[str, tuple[FixtureLearner, Learner]]
QUIZ_LENGTH = 10
OPTIONS = 4


async def levels_of(db: Databases, word_ids: list[str]) -> dict[str, int]:
    async with db.dictionary.connect() as connection:
        rows = await connection.execute(
            text("SELECT id, level FROM ojlpt.vocab WHERE id = ANY(:ids)"), {"ids": word_ids}
        )
        return {str(row[0]): int(row[1]) for row in rows}


@pytest.mark.parametrize("name", ["ayu", "budi", "citra"])
async def test_a_quiz_has_ten_distinct_words_each_with_four_distinct_options(
    engine_databases: Databases, fixtures_and_learners: Replayed, name: str
) -> None:
    _, learner = fixtures_and_learners[name]
    quiz = await make_quiz(engine_databases, learner.id, date(2026, 11, 8))
    assert len(quiz.items) == QUIZ_LENGTH
    assert len({item.word_id for item in quiz.items}) == QUIZ_LENGTH
    for item in quiz.items:
        assert len(item.options) == OPTIONS
        assert len(set(item.options)) == OPTIONS, item


async def test_the_same_day_and_batch_give_the_same_quiz_and_another_batch_differs(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, budi = fixtures_and_learners["budi"]
    first = await make_quiz(engine_databases, budi.id, date(2026, 11, 8))
    again = await make_quiz(engine_databases, budi.id, date(2026, 11, 8))
    other = await make_quiz(engine_databases, budi.id, date(2026, 11, 8), batch=1)
    assert first == again
    assert [item.word_id for item in other.items] != [item.word_id for item in first.items]


async def test_due_mistakes_come_first(engine_databases: Databases, fixtures_and_learners: Replayed) -> None:
    _, budi = fixtures_and_learners["budi"]
    quiz = await make_quiz(engine_databases, budi.id, date(2026, 11, 8))
    assert [item.prompt for item in quiz.items[:2]] == ["川", "山"]


async def correct_option(db: Databases, learner: Learner, item: QuizItem) -> str:
    graded = await grade_answer(db, learner.id, item.word_id, item.kind, "not an option", datetime.now(UTC))
    return graded.correct_option


async def test_every_option_is_from_the_words_level_or_the_correct_answer(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, citra = fixtures_and_learners["citra"]
    quiz = await make_quiz(engine_databases, citra.id, date(2026, 11, 9))
    async with engine_databases.dictionary.connect() as connection:
        for item in quiz.items:
            level = await connection.scalar(text("SELECT level FROM ojlpt.vocab WHERE id = :id"), {"id": item.word_id})
            column = "reading" if item.kind == "reading" else "meanings->>0"
            same_level = set(
                await connection.scalars(
                    text(f"SELECT {column} FROM ojlpt.vocab WHERE level = :level"),
                    {"level": level},
                )
            )
            distractors = [option for option in item.options if option not in same_level]
            assert len(distractors) <= 1, (item, distractors)  # at most the correct answer's full gloss


async def test_a_kana_only_word_is_only_asked_for_its_meaning(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, ayu = fixtures_and_learners["ayu"]
    for batch in range(3):
        for item in (await make_quiz(engine_databases, ayu.id, date(2026, 11, 8), batch=batch)).items:
            if all("぀" <= char <= "ヿ" for char in item.prompt):
                assert item.kind == "meaning", item


async def test_grading_the_right_option_is_correct_and_any_other_is_not(
    engine_databases: Databases, fixtures_and_learners: Replayed
) -> None:
    _, ayu = fixtures_and_learners["ayu"]
    item = (await make_quiz(engine_databases, ayu.id, date(2026, 11, 8))).items[0]
    right = await correct_option(engine_databases, ayu, item)
    assert right in item.options
    wrong = next(option for option in item.options if option != right)
    assert (await grade_answer(engine_databases, ayu.id, item.word_id, item.kind, right, datetime.now(UTC))).is_correct
    graded = await grade_answer(engine_databases, ayu.id, item.word_id, item.kind, wrong, datetime.now(UTC))
    assert not graded.is_correct
