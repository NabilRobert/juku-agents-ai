"""The placement test (the curriculum, 2026-11-05): where on the path a learner who already knows some starts.

A learner aiming at N2 shouldn't start at N5's unit 1. The test takes one level at a time: a word from each
of up to PLACEMENT_QUESTIONS units spread evenly through it, asked as the quiz asks (questions_for). The
answers are graded by the server, never the page, and recorded like any quiz answer.

The learner is placed through the last unit they answered right before their second wrong answer, in the
path's order: one slip is forgiven, but a wrong answer never places them past anything. With at most one
wrong answer they pass the whole level, and can take the next. Every word in
the units placed through is marked known, and the placement is an event (placed), so those units count as
done in the curriculum even before their sentences are read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.engine import quiz, writes
from juku_data.engine.models import EngineModel, Learner, Quiz, QuizKind
from juku_data.engine.recompute import MARKED_KNOWN

PLACEMENT_QUESTIONS = 15
# A wrong answer is forgiven; the second one ends the placement.
WRONG_ANSWERS_ALLOWED = 1

LEVEL_UNITS = "SELECT unit_id FROM ojlpt.curriculum_unit WHERE level = :level ORDER BY unit_id"
FIRST_WORDS = (
    "SELECT DISTINCT ON (unit_id) unit_id, word_id FROM ojlpt.curriculum_word "
    "WHERE unit_id = ANY(:units) ORDER BY unit_id, position"
)
# Every word up to the unit placed through: the path runs N5 to N2, so placing in N4 passes all of N5 too.
WORDS_THROUGH = "SELECT word_id FROM ojlpt.curriculum_word WHERE unit_id <= :through"
KNOWN = "SELECT item_id FROM learning.learner_state WHERE learner_id = :learner AND is_known"


@dataclass(frozen=True)
class PlacementAnswer:
    word_id: str
    kind: QuizKind
    chosen: str


class PlacementResult(EngineModel):
    level: int
    correct: int
    total: int
    placed_through_unit_id: int  # 0 if not even the level's first unit
    passed_level: bool


def sampled_units(units: list[int], count: int = PLACEMENT_QUESTIONS) -> list[int]:
    """Up to `count` units spread evenly through the level, its first and last included."""
    if len(units) <= count:
        return units
    return sorted({units[round(index * (len(units) - 1) / (count - 1))] for index in range(count)})


async def placement_questions(dictionary: AsyncEngine, learner: Learner, level: int) -> Quiz:
    async with dictionary.connect() as connection:
        units = list(await connection.scalars(text(LEVEL_UNITS), {"level": level}))
        rows = (await connection.execute(text(FIRST_WORDS), {"units": sampled_units(units)})).all()
    word_ids = [str(row.word_id) for row in rows]
    return Quiz(items=await quiz.questions_for(dictionary, word_ids, f"{learner.public_id}:placement:{level}"))


def placed_through(results: list[tuple[int, bool]], level_units: list[int]) -> int:
    """The last unit answered right before the second wrong answer; the level's last with at most one wrong.

    `results` is (unit ID, answered right) for each question; 0 means not even the level's first unit.
    """
    wrong = 0
    last_right = 0
    for unit_id, is_right in sorted(results):
        if is_right:
            last_right = unit_id
            continue
        wrong += 1
        if wrong > WRONG_ANSWERS_ALLOWED:
            return last_right
    return level_units[-1] if level_units else 0


async def _unit_of(dictionary: AsyncEngine, word_ids: list[str]) -> dict[str, int]:
    async with dictionary.connect() as connection:
        rows = await connection.execute(
            text("SELECT word_id, unit_id FROM ojlpt.curriculum_word WHERE word_id = ANY(:ids)"), {"ids": word_ids}
        )
        return {str(row.word_id): int(row.unit_id) for row in rows}


async def _graded(dictionary: AsyncEngine, answers: list[PlacementAnswer]) -> list[tuple[PlacementAnswer, bool]]:
    """Each answer checked against the answer looked up again; answers to words that can't be quizzed dropped."""
    graded: list[tuple[PlacementAnswer, bool]] = []
    for answer in answers:
        correct = await quiz.correct_option(dictionary, answer.word_id, answer.kind)
        if correct is not None:
            graded.append((answer, answer.chosen == correct))
    return graded


async def place(  # noqa: PLR0913 (the learner, the level, their answers, and when)
    app: AsyncEngine,
    dictionary: AsyncEngine,
    learner: Learner,
    level: int,
    answers: list[PlacementAnswer],
    at: datetime,
) -> PlacementResult:
    graded = await _graded(dictionary, answers)
    units_of = await _unit_of(dictionary, [answer.word_id for answer, _ in graded])
    async with dictionary.connect() as connection:
        level_units = [int(unit) for unit in await connection.scalars(text(LEVEL_UNITS), {"level": level})]
    results = [(units_of[answer.word_id], is_right) for answer, is_right in graded if answer.word_id in units_of]
    through = placed_through(results, level_units)
    async with dictionary.connect() as connection:
        to_know = [str(word) for word in await connection.scalars(text(WORDS_THROUGH), {"through": through})]
    async with app.begin() as connection:
        for answer, is_right in graded:
            await writes.apply_word_event(
                connection, learner.id, answer.word_id, writes.QUIZ_EVENT[answer.kind], at, is_correct=is_right
            )
        known = {str(item) for item in await connection.scalars(text(KNOWN), {"learner": learner.id})}
        for word_id in to_know:
            if word_id not in known:
                await writes.apply_word_event(connection, learner.id, word_id, MARKED_KNOWN, at)
        if through:
            await writes.apply_placement(connection, learner.id, through, at)
    return PlacementResult(
        level=level,
        correct=sum(1 for _, is_right in graded if is_right),
        total=len(graded),
        placed_through_unit_id=through,
        passed_level=bool(level_units) and through == level_units[-1],
    )
