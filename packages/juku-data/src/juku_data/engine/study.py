"""Studying words in context: a word's examples, the grammar points, a sentence explained, a kanji's readings.

All $0 and all from the dict database (OpenJLPT, and the sentence breakdowns built when it loads); the app
database only says which words the learner knows. Postgres can't join across the two (ADR-006), so the
known words come in as a list.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.dictionary.furigana import checked_furigana
from juku_data.engine.models import (
    BreakdownToken,
    Example,
    GrammarPoint,
    GrammarSummary,
    KanjiEntry,
    KanjiWord,
    SentenceBreakdown,
    TokenWord,
    WordEntry,
)
from juku_data.engine.reads import known_word_ids

WORD_EXAMPLES_SHOWN = 5
KANJI_WORDS_SHOWN = 8

WORDS_WITH_LEVEL = """
SELECT id, word, reading, level, meanings FROM ojlpt.vocab WHERE id = ANY(:ids)
UNION ALL
SELECT id, word, reading, NULL, to_jsonb(string_to_array(meanings, '; ')) FROM ojlpt.supplement_word
WHERE id = ANY(:ids)
"""
WORD_EXAMPLES = "SELECT ja, furigana, en FROM ojlpt.vocab_example WHERE vocab_id = :id ORDER BY ord LIMIT :limit"
GRAMMAR_COLUMNS = "id, pattern, level, meaning"
GRAMMAR_AT_LEVEL = f"""
SELECT {GRAMMAR_COLUMNS} FROM ojlpt.grammar JOIN ojlpt.grammar_position USING (id)
WHERE level = :level ORDER BY position
"""  # noqa: S608 (constant columns)
GRAMMAR_BY_IDS = f"SELECT {GRAMMAR_COLUMNS} FROM ojlpt.grammar WHERE id = ANY(:ids)"  # noqa: S608
GRAMMAR_POINT = "SELECT id, pattern, level, meaning, formation, notes, examples FROM ojlpt.grammar WHERE id = :id"
BREAKDOWNS = "SELECT ja, tokens, grammar_ids FROM ojlpt.sentence_breakdown WHERE ja = ANY(:texts)"
KANJI = "SELECT character, level, strokes, onyomi, kunyomi, meanings FROM ojlpt.kanji WHERE character = :kanji"
# The learner's known words first (how they already read it), then the easiest and most common.
KANJI_WORDS = """
SELECT wl.id, wl.word, wl.reading, wl.level, v.meanings ->> 0 AS meaning, wl.id = ANY(:known) AS is_known
FROM ojlpt.word_kanji wk JOIN ojlpt.word_level wl USING (id) JOIN ojlpt.vocab v USING (id)
WHERE wk.kanji = :kanji
ORDER BY is_known DESC, wl.level DESC, wl.commonness, wl.id
LIMIT :limit
"""


def _json(value: Any) -> Any:
    # asyncpg hands jsonb back as text unless a codec is set; the engine's other reads do the same.
    return json.loads(value) if isinstance(value, str) else value


def _example(ja: str, furigana: str | None, en: str | None) -> Example:
    return Example(ja=ja, furigana=checked_furigana(ja, furigana), en=en)


def _summary(row: Any) -> GrammarSummary:
    return GrammarSummary(grammar_id=row.id, pattern=row.pattern, level=row.level, meaning=row.meaning)


async def _words(dictionary: AsyncEngine, ids: list[str], known: set[str]) -> dict[str, TokenWord]:
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(WORDS_WITH_LEVEL), {"ids": ids})).all()
    return {
        row.id: TokenWord(
            word_id=row.id,
            word=row.word,
            reading=row.reading,
            level=row.level,
            meanings=[str(meaning) for meaning in _json(row.meanings)],
            is_known=row.id in known,
        )
        for row in rows
    }


async def word_entry(app: AsyncEngine, dictionary: AsyncEngine, learner_id: int, word_id: str) -> WordEntry | None:
    """The word and up to five examples of it in use; None if there's no such word."""
    known = set(await known_word_ids(app, learner_id))
    word = (await _words(dictionary, [word_id], known)).get(word_id)
    if word is None:
        return None
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(WORD_EXAMPLES), {"id": word_id, "limit": WORD_EXAMPLES_SHOWN})).all()
    return WordEntry(**word.model_dump(), examples=[_example(row.ja, row.furigana, row.en) for row in rows])


async def grammar_at_level(dictionary: AsyncEngine, level: int) -> list[GrammarSummary]:
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(GRAMMAR_AT_LEVEL), {"level": level})).all()
    return [_summary(row) for row in rows]


async def grammar_point(dictionary: AsyncEngine, grammar_id: str) -> GrammarPoint | None:
    async with dictionary.connect() as connection:
        row = (await connection.execute(text(GRAMMAR_POINT), {"id": grammar_id})).first()
    if row is None:
        return None
    examples = [_example(item["ja"], item.get("furigana"), item.get("en")) for item in _json(row.examples)]
    return GrammarPoint(**_summary(row).model_dump(), formation=row.formation, notes=row.notes, examples=examples)


async def explain_sentences(
    app: AsyncEngine, dictionary: AsyncEngine, learner_id: int, sentences: list[str]
) -> dict[str, SentenceBreakdown]:
    """Each sentence's breakdown, by its text; a sentence with none (not an example) is left out."""
    async with dictionary.connect() as connection:
        rows = (await connection.execute(text(BREAKDOWNS), {"texts": sentences})).all()
        stored = {row.ja: (_json(row.tokens), _json(row.grammar_ids)) for row in rows}
        grammar_ids = sorted({grammar_id for _, ids in stored.values() for grammar_id in ids})
        grammar_rows = (await connection.execute(text(GRAMMAR_BY_IDS), {"ids": grammar_ids})).all()
    grammar = {row.id: _summary(row) for row in grammar_rows}
    word_ids = sorted({word_id for tokens, _ in stored.values() for token in tokens for word_id in token["word_ids"]})
    words = await _words(dictionary, word_ids, set(await known_word_ids(app, learner_id)))
    return {ja: _breakdown(ja, tokens, ids, words, grammar) for ja, (tokens, ids) in stored.items()}


def _breakdown(
    ja: str,
    tokens: list[dict[str, Any]],
    grammar_ids: list[str],
    words: dict[str, TokenWord],
    grammar: dict[str, GrammarSummary],
) -> SentenceBreakdown:
    shown = [
        BreakdownToken(
            surface=token["surface"],
            reading=token["reading"],
            kind=token["kind"],
            words=[words[word_id] for word_id in token["word_ids"] if word_id in words],
        )
        for token in tokens
    ]
    # Easiest first: N5 (level 5) before N4, and so on.
    used = sorted((grammar[grammar_id] for grammar_id in grammar_ids), key=lambda point: (-point.level, point.pattern))
    return SentenceBreakdown(ja=ja, tokens=shown, grammar=used)


async def kanji_entry(app: AsyncEngine, dictionary: AsyncEngine, learner_id: int, kanji: str) -> KanjiEntry | None:
    """The kanji's readings and meanings, and words that show how it's read; None if it isn't a JLPT kanji."""
    known = await known_word_ids(app, learner_id)
    async with dictionary.connect() as connection:
        row = (await connection.execute(text(KANJI), {"kanji": kanji})).first()
        if row is None:
            return None
        words = (
            await connection.execute(text(KANJI_WORDS), {"kanji": kanji, "known": known, "limit": KANJI_WORDS_SHOWN})
        ).all()
    return KanjiEntry(
        character=row.character,
        level=row.level,
        strokes=row.strokes,
        onyomi=list(_json(row.onyomi)),
        kunyomi=list(_json(row.kunyomi)),
        meanings=list(_json(row.meanings)),
        words=[
            KanjiWord(
                word_id=word.id,
                word=word.word,
                reading=word.reading,
                level=word.level,
                meaning=word.meaning,
                is_known=word.is_known,
            )
            for word in words
        ],
    )
