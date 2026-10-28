"""An independent, plain-Python reading of ADR-010 and LE4, used to check the engine's SQL.

It is written from the decision's text, not from the engine's code, and is
deliberately naive: loops over the whole dictionary, no incremental state.
If the engine and the oracle disagree, one of them misreads the rules.
It also generated the committed expected outputs, before the engine
existed (EDD1).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

RECOMMENDATIONS = 10
MAX_PER_NEW_KANJI = 3
SENTENCES = 10


@dataclass(frozen=True)
class OracleWord:
    id: str
    word: str
    reading: str
    level: int
    commonness: int


@dataclass
class OracleDictionary:
    words: list[OracleWord]
    word_kanji: dict[str, set[str]]
    kanji_level: dict[str, int]
    leverage: dict[tuple[str, int], int]
    sentence_words: dict[int, set[str]]
    sentence_text: dict[int, str]


async def load_oracle_dictionary(dict_engine: AsyncEngine) -> OracleDictionary:
    async with dict_engine.connect() as connection:
        words = [
            OracleWord(str(row[0]), str(row[1]), str(row[2]), int(row[3]), int(row[4]))
            for row in await connection.execute(
                text("SELECT id, word, reading, level, commonness FROM ojlpt.word_level")
            )
        ]
        word_kanji: dict[str, set[str]] = defaultdict(set)
        for word_id, kanji in await connection.execute(text("SELECT id, kanji FROM ojlpt.word_kanji")):
            word_kanji[str(word_id)].add(str(kanji))
        kanji_level = {
            str(row[0]): int(row[1])
            for row in await connection.execute(text("SELECT character, level FROM ojlpt.kanji"))
        }
        leverage: dict[tuple[str, int], int] = {}
        for kanji, level, count in await connection.execute(
            text("SELECT kanji, level, words FROM ojlpt.kanji_leverage")
        ):
            leverage[(str(kanji), int(level))] = int(count)
        sentence_words: dict[int, set[str]] = defaultdict(set)
        for sentence_id, word_id in await connection.execute(
            text("SELECT sentence_id, word_id FROM ojlpt.sentence_word")
        ):
            sentence_words[int(sentence_id)].add(str(word_id))
        sentence_text = {
            int(row[0]): str(row[1])
            for row in await connection.execute(text("SELECT sentence_id, ja FROM ojlpt.sentence"))
        }
    return OracleDictionary(words, dict(word_kanji), kanji_level, leverage, dict(sentence_words), sentence_text)


def recommend(dictionary: OracleDictionary, known: set[str], target_level: int) -> list[dict[str, Any]]:
    """ADR-010, read literally: candidates, the lexicographic order, then the variety cap."""
    known_kanji = {kanji for kanji, level in dictionary.kanji_level.items() if level > target_level}
    for word_id in known:
        known_kanji |= dictionary.word_kanji.get(word_id, set())
    candidates: list[tuple[tuple[int, int, int, str], OracleWord, str | None, int]] = []
    for word in dictionary.words:
        if word.level < target_level or word.id in known:
            continue
        unknown_kanji = sorted(dictionary.word_kanji.get(word.id, set()) - known_kanji)
        if len(unknown_kanji) > 1:
            continue
        new_kanji = unknown_kanji[0] if unknown_kanji else None
        leverage = dictionary.leverage.get((new_kanji, target_level), 0) if new_kanji else 0
        is_gap = word.level > target_level
        order = (0 if is_gap else 1, -leverage, word.commonness, word.id)
        candidates.append((order, word, new_kanji, leverage))
    candidates.sort(key=lambda candidate: candidate[0])
    picked: list[dict[str, Any]] = []
    per_kanji: Counter[str] = Counter()
    for _, word, new_kanji, leverage in candidates:
        if new_kanji is not None and per_kanji[new_kanji] >= MAX_PER_NEW_KANJI:
            continue
        if new_kanji is not None:
            per_kanji[new_kanji] += 1
        picked.append(
            {"word_id": word.id, "word": word.word, "level": word.level, "new_kanji": new_kanji, "leverage": leverage}
        )
        if len(picked) == RECOMMENDATIONS:
            break
    return picked


def reading_sentences(dictionary: OracleDictionary, known: set[str]) -> list[dict[str, Any]]:
    """LE4: sentences with exactly one unknown word, shortest first, then by ID."""
    found: list[tuple[int, int, str]] = []
    for sentence_id, words in dictionary.sentence_words.items():
        unknown = words - known
        if len(unknown) == 1:
            found.append((len(dictionary.sentence_text[sentence_id]), sentence_id, next(iter(unknown))))
    found.sort()
    return [{"sentence_id": sentence_id, "new_word_id": word_id} for _, sentence_id, word_id in found[:SENTENCES]]
