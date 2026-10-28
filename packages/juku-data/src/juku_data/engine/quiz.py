"""Quizzes, generated and graded in code (Phase 2 LE2). No model call.

Which words, in order, ten to a batch:
1. Leitner items due by the end of the learner's day (the mistakes queue);
2. words in progress: answered before, not yet known, most recent first;
3. Susumu's recommendations, in rank order.

Each word is asked for its meaning or its reading (kana-only words: always
the meaning). The three distractors are words of the same level, those
sharing a kanji with it first, then those with a reading of the same
length. Every choice is ordered by a hash of the learner, the day and the
batch, so a quiz is the same if reloaded and different the next day,
without storing it.

Grading needs no stored quiz either: the right answer is looked up again
from the word and the question's kind, so a client can't send its own.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.dictionary.sentences import is_kana
from juku_data.engine.models import GradedAnswer, Learner, Quiz, QuizItem, QuizKind
from juku_data.engine.reads import ranked_candidates

QUIZ_LENGTH = 10
DISTRACTORS = 3
# How many recommendations to draw on, so later batches still have words.
RECOMMENDATION_POOL = 60


DUE_ITEMS = """
SELECT item_id FROM learning.learner_state
WHERE learner_id = :learner_id AND box IS NOT NULL AND due_at < :end_of_day ORDER BY due_at, item_id
"""
IN_PROGRESS = """
SELECT item_id FROM learning.learner_state
WHERE learner_id = :learner_id AND NOT is_known AND box IS NULL AND correct_count + wrong_count > 0
ORDER BY last_seen_at DESC, item_id
"""


@dataclass(frozen=True)
class QuizWord:
    id: str
    word: str
    reading: str
    level: int
    first_meaning: str
    kanji: frozenset[str]

    @property
    def is_kana_only(self) -> bool:
        return is_kana(self.word)

    def option(self, kind: QuizKind) -> str:
        return self.reading if kind == "reading" else self.first_meaning


def stable_hash(*parts: object) -> int:
    """A number from the parts, the same on every run (Python's hash() isn't)."""
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


async def _picked_word_ids(app: AsyncEngine, learner: Learner, today: date) -> list[str]:
    end_of_day = datetime.combine(today + timedelta(days=1), time(), tzinfo=ZoneInfo(learner.timezone))
    async with app.connect() as connection:
        due = await connection.scalars(text(DUE_ITEMS), {"learner_id": learner.id, "end_of_day": end_of_day})
        in_progress = await connection.scalars(text(IN_PROGRESS), {"learner_id": learner.id})
        picked = [str(word_id) for word_id in due] + [str(word_id) for word_id in in_progress]
    _, ranked = await ranked_candidates(app, learner.id, RECOMMENDATION_POOL)
    picked += [word_id for word_id, *_ in ranked]
    unique: list[str] = []
    for word_id in picked:
        if word_id not in unique:
            unique.append(word_id)
    return unique


QUIZ_WORDS = """
SELECT v.id, v.word, v.reading, v.level, v.meanings,
       coalesce(array_agg(wk.kanji) FILTER (WHERE wk.kanji IS NOT NULL), '{}')
FROM ojlpt.vocab v LEFT JOIN ojlpt.word_kanji wk USING (id)
WHERE {condition}
GROUP BY v.id
"""


async def _quiz_words(dictionary: AsyncEngine, condition: str, parameters: dict[str, Any]) -> list[QuizWord]:
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(QUIZ_WORDS.replace("{condition}", condition)), parameters)).all()
    words: list[QuizWord] = []
    for word_id, word, reading, level, meanings, kanji in rows:
        parsed: Any = json.loads(meanings) if isinstance(meanings, str) else meanings
        words.append(QuizWord(str(word_id), str(word), str(reading), int(level), str(parsed[0]), frozenset(kanji)))
    return words


async def _words_at_levels(dictionary: AsyncEngine, levels: set[int]) -> list[QuizWord]:
    return await _quiz_words(dictionary, "v.level = ANY(:levels)", {"levels": sorted(levels)})


async def _quiz_word(dictionary: AsyncEngine, word_id: str) -> QuizWord | None:
    found = await _quiz_words(dictionary, "v.id = :id", {"id": word_id})
    return found[0] if found else None


def _kind_for(word: QuizWord, seed: str) -> QuizKind:
    if word.is_kana_only:
        return "meaning"
    return "reading" if stable_hash(seed, word.id, "kind") % 2 else "meaning"


def _options(word: QuizWord, kind: QuizKind, same_level: list[QuizWord], seed: str) -> list[str]:
    correct = word.option(kind)

    def preference(other: QuizWord) -> tuple[int, int, int]:
        shares_kanji = bool(word.kanji & other.kanji)
        similar_reading = len(other.reading) == len(word.reading)
        return (0 if shares_kanji else 1, 0 if similar_reading else 1, stable_hash(seed, word.id, other.id))

    chosen = [correct]
    for other in sorted((other for other in same_level if other.id != word.id), key=preference):
        option = other.option(kind)
        if option not in chosen:
            chosen.append(option)
        if len(chosen) == DISTRACTORS + 1:
            break
    return sorted(chosen, key=lambda option: stable_hash(seed, word.id, option))


async def make_quiz(app: AsyncEngine, dictionary: AsyncEngine, learner: Learner, today: date, batch: int) -> Quiz:
    seed = f"{learner.public_id}:{today.isoformat()}:{batch}"
    picked = (await _picked_word_ids(app, learner, today))[batch * QUIZ_LENGTH : (batch + 1) * QUIZ_LENGTH]
    async with dictionary.connect() as connection:
        levels = {
            int(level)
            for level in await connection.scalars(
                text("SELECT DISTINCT level FROM ojlpt.vocab WHERE id = ANY(:ids)"), {"ids": picked}
            )
        }
    by_level: dict[int, list[QuizWord]] = {}
    by_id: dict[str, QuizWord] = {}
    for word in await _words_at_levels(dictionary, levels):
        by_level.setdefault(word.level, []).append(word)
        by_id[word.id] = word
    items: list[QuizItem] = []
    for word_id in picked:
        word = by_id.get(word_id)
        if word is None:  # a supplement word has no level, so no distractors: it isn't quizzed
            continue
        kind = _kind_for(word, seed)
        items.append(
            QuizItem(
                word_id=word.id, kind=kind, prompt=word.word, options=_options(word, kind, by_level[word.level], seed)
            )
        )
    return Quiz(items=items)


async def correct_option(dictionary: AsyncEngine, word_id: str, kind: QuizKind) -> str | None:
    """The one right answer to this word's question of this kind, or None if the word isn't quizzable."""
    word = await _quiz_word(dictionary, word_id)
    return None if word is None else word.option(kind)


def graded(word_id: str, kind: QuizKind, chosen: str, correct: str) -> GradedAnswer:
    return GradedAnswer(word_id=word_id, kind=kind, is_correct=chosen == correct, correct_option=correct)
