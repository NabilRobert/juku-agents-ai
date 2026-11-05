"""What the learning engine returns: typed, so the MCP tools and pages share one contract.

Every model is frozen and refuses unknown fields. They hold facts the
engine computed in SQL and Python, never anything a model wrote.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class EngineModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


QuizKind = Literal["meaning", "reading"]


def level_name(level: int) -> str:
    """OpenJLPT's number as the name learners know: 5 -> "N5"."""
    return f"N{level}"


class Learner(EngineModel):
    id: int
    public_id: str
    cohort_id: int
    target_level: int
    timezone: str
    exam_date: date | None


class LevelCoverage(EngineModel):
    level: int
    level_name: str
    words_known: int
    words_total: int
    kanji_known: int
    kanji_total: int
    word_coverage: float
    kanji_coverage: float


class Progress(EngineModel):
    """LE1: how much of each level the learner knows."""

    target_level: int
    known_words: int
    levels: list[LevelCoverage]


class RecommendedWord(EngineModel):
    word_id: str
    word: str
    reading: str
    level: int
    meanings: list[str]
    new_kanji: str | None
    leverage: int
    reason: str


class KnownWord(EngineModel):
    word_id: str
    word: str
    reading: str


class KnownWords(EngineModel):
    """The words the learner knows, latest first, for the memory page (MEM-R5); `total` counts them all."""

    items: list[KnownWord]
    total: int


class Recommendations(EngineModel):
    """LE3: ten words to learn next (Susumu), each with its reason."""

    words: list[RecommendedWord]


class MistakeItem(EngineModel):
    word_id: str
    word: str
    reading: str
    box: int
    due_at: datetime
    is_due: bool


class Mistakes(EngineModel):
    """LE6: the Leitner queue, due items first."""

    items: list[MistakeItem]


class ReadingSentence(EngineModel):
    sentence_id: int
    ja: str
    furigana: str | None
    en: str | None
    tatoeba_id: int | None
    new_word_id: str
    new_word: str


class ReadingSentences(EngineModel):
    """LE4: sentences where every word is known but one."""

    sentences: list[ReadingSentence]


class Plan(EngineModel):
    """LE5: the pace needed to reach the target coverage by the exam."""

    target_level: int
    target_coverage: float
    words_in_scope: int
    words_known: int
    words_needed: int
    exam_date: date | None
    weeks_left: int | None
    words_per_week: int | None
    formula: str


class DayActivity(EngineModel):
    day: date
    quiz_answers: int
    quiz_correct: int
    words_marked: int
    sentences_read: int


class RecentActivity(EngineModel):
    days: list[DayActivity]


class QuizItem(EngineModel):
    """One question. The answer isn't in it: grading looks it up again (LE2)."""

    word_id: str
    kind: QuizKind
    prompt: str
    options: list[str]


class Quiz(EngineModel):
    items: list[QuizItem]


class GradedAnswer(EngineModel):
    word_id: str
    kind: QuizKind
    is_correct: bool
    correct_option: str


class Example(EngineModel):
    """An example sentence from the dictionary (Tatoeba's or OpenJLPT's), with its furigana if it checks out."""

    ja: str
    furigana: str | None
    en: str | None


class WordEntry(EngineModel):
    """One word's page: what it means, and how it's used (its example sentences)."""

    word_id: str
    word: str
    reading: str
    level: int | None  # None for a supplement word, which is in no JLPT list
    meanings: list[str]
    is_known: bool
    examples: list[Example]


class GrammarSummary(EngineModel):
    grammar_id: str
    pattern: str
    level: int
    meaning: str


class GrammarPoint(EngineModel):
    """One sentence structure: how it's formed, what it means, and examples."""

    grammar_id: str
    pattern: str
    level: int
    meaning: str
    formation: str
    notes: str | None
    examples: list[Example]


class TokenWord(EngineModel):
    word_id: str
    word: str
    reading: str
    level: int | None
    meanings: list[str]
    is_known: bool


class BreakdownToken(EngineModel):
    surface: str
    reading: str
    kind: Literal["word", "grammar", "name", "number", "symbol"]
    words: list[TokenWord]


class SentenceBreakdown(EngineModel):
    """A sentence explained from the data: its words, and the grammar points it may use (easiest first)."""

    ja: str
    tokens: list[BreakdownToken]
    grammar: list[GrammarSummary]


class KanjiWord(EngineModel):
    word_id: str
    word: str
    reading: str
    level: int
    meaning: str
    is_known: bool


class KanjiEntry(EngineModel):
    """One kanji: its readings, what it means, and words that use it (the learner's known ones first)."""

    character: str
    level: int
    strokes: int | None
    onyomi: list[str]
    kunyomi: list[str]
    meanings: list[str]
    words: list[KanjiWord]
