"""The curriculum's answers for one learner (engine/curriculum.py): typed, so the pages and tools share them."""

from __future__ import annotations

from typing import Literal

from juku_data.engine.models import EngineModel


class UnitStatus(EngineModel):
    unit_id: int
    level: int
    number: int
    words_total: int
    words_known: int
    grammar_total: int
    grammar_studied: int
    sentences_total: int
    sentences_read: int
    status: Literal["done", "current", "later"]


class CurriculumLevel(EngineModel):
    level: int
    units: list[UnitStatus]


class CurriculumOverview(EngineModel):
    target_level: int
    units_total: int
    units_done: int
    current_unit_id: int | None  # None once every unit up to the target is done
    levels: list[CurriculumLevel]


class UnitWord(EngineModel):
    word_id: str
    word: str
    reading: str
    meanings: list[str]
    is_known: bool


class UnitGrammar(EngineModel):
    grammar_id: str
    pattern: str
    meaning: str
    is_studied: bool


class UnitSentence(EngineModel):
    sentence_id: int
    ja: str
    furigana: str | None
    en: str | None
    is_read: bool


class UnitDetail(EngineModel):
    unit: UnitStatus
    words: list[UnitWord]
    kanji: list[str]
    grammar: list[UnitGrammar]
    sentences: list[UnitSentence]
    previous_unit_id: int | None
    next_unit_id: int | None


class TodayPlan(EngineModel):
    """Today's lesson from the current unit, each part with its target and what's done so far today."""

    unit: UnitStatus | None
    new_words: list[UnitWord]
    words_target: int
    words_done: int
    grammar: UnitGrammar | None
    grammar_done: int
    sentences: list[UnitSentence]
    sentences_target: int
    sentences_done: int
    reviews_due: int
    quiz_target: int
    quiz_done: int
