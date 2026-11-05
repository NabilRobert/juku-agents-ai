"""The curriculum, for one learner: where they are on the path, a unit's contents, and today's lesson.

The path itself is dictionary data (dictionary/curriculum.py, built at load). This module joins it with
what the learner has done: their known words (learner_state), the grammar points they've studied and the
sentences they've read (learner_studied), their due reviews and today's counts. Summaries only (FF2), $0.

A unit is done when all its words are known, its grammar points studied and its sentences read. The
current unit is the first not done, from N5 up to the learner's target level.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.dictionary.furigana import checked_furigana
from juku_data.engine.curriculum_models import (
    CurriculumLevel,
    CurriculumOverview,
    TodayPlan,
    UnitDetail,
    UnitGrammar,
    UnitSentence,
    UnitStatus,
    UnitWord,
)
from juku_data.engine.models import Learner
from juku_data.engine.recompute import GRAMMAR_STUDIED, PLACED, SENTENCE_READ

# Today's lesson: words a day from the plan's pace, within these bounds; this many without an exam date.
DEFAULT_WORDS_A_DAY = 10
WORDS_A_DAY_BOUNDS = (3, 30)
SENTENCES_A_DAY = 3
QUIZ_A_DAY = 10

PATH = "SELECT unit_id, level, number FROM ojlpt.curriculum_unit WHERE level >= :target ORDER BY unit_id"
# Each kind of item a unit holds: its table, and the column naming the item.
UNIT_ITEM_TABLES = {
    "words": ("curriculum_word", "word_id"),
    "kanji": ("curriculum_kanji", "kanji"),
    "grammar": ("curriculum_grammar", "grammar_id"),
    "sentences": ("curriculum_sentence", "sentence_id::text"),
}
UNIT_ITEMS = {
    name: f"SELECT unit_id, {column} FROM ojlpt.{table} WHERE unit_id = ANY(:units) ORDER BY unit_id, position"  # noqa: S608
    for name, (table, column) in UNIT_ITEM_TABLES.items()
}
STUDIED = "SELECT kind, item_id, first_at FROM learning.learner_studied WHERE learner_id = :learner"
KNOWN = "SELECT item_id FROM learning.learner_state WHERE learner_id = :learner AND is_known"
WORDS = "SELECT id, word, reading, meanings FROM ojlpt.vocab WHERE id = ANY(:ids)"
GRAMMAR = "SELECT id, pattern, meaning FROM ojlpt.grammar WHERE id = ANY(:ids)"
SENTENCES = "SELECT sentence_id, ja, furigana, en FROM ojlpt.sentence WHERE sentence_id = ANY(:ids)"
TODAY = (
    "SELECT quiz_answers, words_marked, sentences_read FROM learning.learner_daily_activity "
    "WHERE learner_id = :learner AND day = :today"
)
DUE_REVIEWS = (
    "SELECT count(*) FROM learning.learner_state WHERE learner_id = :learner AND box IS NOT NULL AND due_at <= :now"
)


@dataclass
class _Unit:
    unit_id: int
    level: int
    number: int
    items: dict[str, list[str]] = field(default_factory=dict[str, list[str]])


@dataclass(frozen=True)
class _Learned:
    known: frozenset[str]
    grammar: dict[str, datetime]
    sentences: dict[str, datetime]
    placed_through: int  # the last unit a placement test placed the learner through; 0 for none


async def _path(dictionary: AsyncEngine, target_level: int) -> list[_Unit]:
    async with dictionary.connect() as connection:
        units = [
            _Unit(row.unit_id, row.level, row.number)
            for row in await connection.execute(text(PATH), {"target": target_level})
        ]
        by_id = {unit.unit_id: unit for unit in units}
        for name, query in UNIT_ITEMS.items():
            for unit in units:
                unit.items[name] = []
            for unit_id, item in await connection.execute(text(query), {"units": list(by_id)}):
                by_id[unit_id].items[name].append(str(item))
    return units


async def _learned(app: AsyncEngine, learner_id: int) -> _Learned:
    async with app.connect() as connection:
        known = frozenset(str(item) for item in await connection.scalars(text(KNOWN), {"learner": learner_id}))
        studied = (await connection.execute(text(STUDIED), {"learner": learner_id})).all()
    grammar = {row.item_id: row.first_at for row in studied if row.kind == GRAMMAR_STUDIED}
    sentences = {row.item_id: row.first_at for row in studied if row.kind == SENTENCE_READ}
    placed = [int(row.item_id) for row in studied if row.kind == PLACED]
    return _Learned(known=known, grammar=grammar, sentences=sentences, placed_through=max(placed, default=0))


def _counts(unit: _Unit, learned: _Learned) -> tuple[int, int, int]:
    return (
        sum(1 for word_id in unit.items["words"] if word_id in learned.known),
        sum(1 for grammar_id in unit.items["grammar"] if grammar_id in learned.grammar),
        sum(1 for sentence_id in unit.items["sentences"] if sentence_id in learned.sentences),
    )


def _statuses(units: Sequence[_Unit], learned: _Learned) -> list[UnitStatus]:
    shown: list[UnitStatus] = []
    current_found = False
    for unit in units:
        words, grammar, sentences = _counts(unit, learned)
        is_complete = (words, grammar, sentences) == tuple(
            len(unit.items[name]) for name in ("words", "grammar", "sentences")
        )
        # A unit a placement test placed the learner through is done, read or not.
        is_done = is_complete or unit.unit_id <= learned.placed_through
        status: Literal["done", "current", "later"] = "done" if is_done else ("later" if current_found else "current")
        current_found = current_found or not is_done
        shown.append(
            UnitStatus(
                unit_id=unit.unit_id,
                level=unit.level,
                number=unit.number,
                words_total=len(unit.items["words"]),
                words_known=words,
                grammar_total=len(unit.items["grammar"]),
                grammar_studied=grammar,
                sentences_total=len(unit.items["sentences"]),
                sentences_read=sentences,
                status=status,
            )
        )
    return shown


async def curriculum_overview(app: AsyncEngine, dictionary: AsyncEngine, learner: Learner) -> CurriculumOverview:
    statuses = _statuses(await _path(dictionary, learner.target_level), await _learned(app, learner.id))
    levels = [
        CurriculumLevel(level=level, units=[status for status in statuses if status.level == level])
        for level in sorted({status.level for status in statuses}, reverse=True)
    ]
    current = next((status.unit_id for status in statuses if status.status == "current"), None)
    done = sum(1 for status in statuses if status.status == "done")
    return CurriculumOverview(
        target_level=learner.target_level,
        units_total=len(statuses),
        units_done=done,
        current_unit_id=current,
        levels=levels,
    )


def _meanings(value: Any) -> list[str]:
    # asyncpg hands jsonb back as text unless a codec is set; the engine's other reads do the same.
    parsed: Any = json.loads(value) if isinstance(value, str) else value
    return [str(meaning) for meaning in parsed]


async def _unit_words(dictionary: AsyncEngine, word_ids: list[str], learned: _Learned) -> list[UnitWord]:
    async with dictionary.connect() as connection:
        rows = {row.id: row for row in await connection.execute(text(WORDS), {"ids": word_ids})}
    return [
        UnitWord(
            word_id=word_id,
            word=rows[word_id].word,
            reading=rows[word_id].reading,
            meanings=_meanings(rows[word_id].meanings),
            is_known=word_id in learned.known,
        )
        for word_id in word_ids
        if word_id in rows
    ]


async def _unit_grammar(dictionary: AsyncEngine, grammar_ids: list[str], learned: _Learned) -> list[UnitGrammar]:
    async with dictionary.connect() as connection:
        rows = {row.id: row for row in await connection.execute(text(GRAMMAR), {"ids": grammar_ids})}
    return [
        UnitGrammar(
            grammar_id=grammar_id,
            pattern=rows[grammar_id].pattern,
            meaning=rows[grammar_id].meaning,
            is_studied=grammar_id in learned.grammar,
        )
        for grammar_id in grammar_ids
        if grammar_id in rows
    ]


async def _unit_sentences(dictionary: AsyncEngine, sentence_ids: list[str], learned: _Learned) -> list[UnitSentence]:
    ids = [int(sentence_id) for sentence_id in sentence_ids]
    async with dictionary.connect() as connection:
        rows = {row.sentence_id: row for row in await connection.execute(text(SENTENCES), {"ids": ids})}
    sentences: list[UnitSentence] = []
    for sentence_id in ids:
        row = rows.get(sentence_id)
        if row is None:
            continue
        sentences.append(
            UnitSentence(
                sentence_id=sentence_id,
                ja=row.ja,
                furigana=checked_furigana(row.ja, row.furigana),
                en=row.en,
                is_read=str(sentence_id) in learned.sentences,
            )
        )
    return sentences


async def unit_detail(app: AsyncEngine, dictionary: AsyncEngine, learner: Learner, unit_id: int) -> UnitDetail | None:
    """One unit of the learner's path, everything in it marked done or not; None if it isn't on their path."""
    units = await _path(dictionary, learner.target_level)
    learned = await _learned(app, learner.id)
    statuses = _statuses(units, learned)
    place = next((index for index, unit in enumerate(units) if unit.unit_id == unit_id), None)
    if place is None:
        return None
    unit = units[place]
    return UnitDetail(
        unit=statuses[place],
        words=await _unit_words(dictionary, unit.items["words"], learned),
        kanji=unit.items["kanji"],
        grammar=await _unit_grammar(dictionary, unit.items["grammar"], learned),
        sentences=await _unit_sentences(dictionary, unit.items["sentences"], learned),
        previous_unit_id=units[place - 1].unit_id if place > 0 else None,
        next_unit_id=units[place + 1].unit_id if place + 1 < len(units) else None,
    )


def words_a_day(words_per_week: int | None) -> int:
    """The plan's weekly pace as a day's words, within WORDS_A_DAY_BOUNDS; a default with no exam date."""
    if words_per_week is None:
        return DEFAULT_WORDS_A_DAY
    low, high = WORDS_A_DAY_BOUNDS
    return min(high, max(low, math.ceil(words_per_week / 7)))


def _done_on(times: dict[str, datetime], today: date, timezone: str) -> int:
    zone = ZoneInfo(timezone)
    return sum(1 for at in times.values() if at.astimezone(zone).date() == today)


async def _today_counts(app: AsyncEngine, learner_id: int, today: date, now: datetime) -> tuple[int, int, int, int]:
    """Quiz answers, words marked and sentences read today, and the reviews due now."""
    async with app.connect() as connection:
        row = (await connection.execute(text(TODAY), {"learner": learner_id, "today": today})).first()
        due = int(await connection.scalar(text(DUE_REVIEWS), {"learner": learner_id, "now": now}) or 0)
    if row is None:
        return 0, 0, 0, due
    return int(row.quiz_answers), int(row.words_marked), int(row.sentences_read), due


def _next_words(units: Sequence[_Unit], start: int, learned: _Learned, count: int) -> list[str]:
    """The next `count` unknown words on the path, from the current unit on."""
    found: list[str] = []
    for unit in units[start:]:
        for word_id in unit.items["words"]:
            if word_id not in learned.known and len(found) < count:
                found.append(word_id)
        if len(found) >= count:
            break
    return found


async def today_plan(  # noqa: PLR0913 (the learner, their pace, and the two clocks)
    app: AsyncEngine, dictionary: AsyncEngine, learner: Learner, words_per_week: int | None, today: date, now: datetime
) -> TodayPlan:
    units = await _path(dictionary, learner.target_level)
    learned = await _learned(app, learner.id)
    statuses = _statuses(units, learned)
    quiz_done, words_done, sentences_done, reviews_due = await _today_counts(app, learner.id, today, now)
    target = words_a_day(words_per_week)
    place = next((index for index, status in enumerate(statuses) if status.status == "current"), None)
    if place is None:
        new_words, grammar, sentences = [], None, []
    else:
        unit = units[place]
        new_words = await _unit_words(
            dictionary, _next_words(units, place, learned, max(0, target - words_done)), learned
        )
        open_grammar = [grammar_id for grammar_id in unit.items["grammar"] if grammar_id not in learned.grammar][:1]
        grammar = next(iter(await _unit_grammar(dictionary, open_grammar, learned)), None)
        unread = [sentence_id for sentence_id in unit.items["sentences"] if sentence_id not in learned.sentences]
        sentences = await _unit_sentences(dictionary, unread[: max(0, SENTENCES_A_DAY - sentences_done)], learned)
    return TodayPlan(
        unit=statuses[place] if place is not None else None,
        new_words=new_words,
        words_target=target,
        words_done=words_done,
        grammar=grammar,
        grammar_done=_done_on(learned.grammar, today, learner.timezone),
        sentences=sentences,
        sentences_target=SENTENCES_A_DAY,
        sentences_done=sentences_done,
        reviews_due=reviews_due,
        quiz_target=QUIZ_A_DAY,
        quiz_done=quiz_done,
    )
