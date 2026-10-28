"""search_words: find a word by kanji, kana, romaji or English (Phase 2 JI1, JI2).

The plan (ADR-003) is to call OpenJLPT's own Python package
(`openjlpt.search_vocab`), installed from the pinned commit. Installing it
needs a git dependency, which waits for Arthur's OK (JOURNEY.md, track B).
Until then this searches the same build in the `dict` database, ranked the
way that package ranks: an exact spelling, then the reading, then romaji,
then an English gloss that is the whole query, then one that contains it
as a word. The tool's contract (its name, schema and output) is the same
either way, so swapping the implementation changes no snapshot.

The query is normalized first (width, case, spaces) and, when it's romaji,
also tried as kana.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from juku_data.japanese import normalize_input, romaji_to_kana, to_hiragana
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

MAX_RESULTS = 10

SEARCH = """
WITH ranked AS (
    SELECT v.id, v.word, v.reading, v.level, v.meanings,
           CASE
               WHEN v.word = :query OR v.other_forms ? :query THEN 0
               WHEN v.reading = :kana OR v.other_readings ? :kana THEN 1
               WHEN v.romaji = :query THEN 2
               WHEN EXISTS (SELECT 1 FROM jsonb_array_elements_text(v.meanings) AS meaning
                            WHERE lower(meaning) IN (:query, 'to ' || :query)) THEN 3
               WHEN EXISTS (SELECT 1 FROM jsonb_array_elements_text(v.meanings) AS meaning
                            WHERE lower(meaning) ~ :whole_word) THEN 4
           END AS rank
    FROM ojlpt.vocab v
)
SELECT id, word, reading, level, meanings FROM ranked
WHERE rank IS NOT NULL
ORDER BY rank, level DESC, id
LIMIT :limit
"""


@dataclass(frozen=True)
class DictionarySearch:
    """The interim word search, over the dict database."""

    dictionary: AsyncEngine

    async def search(self, query: str) -> list[dict[str, Any]]:
        normalized = normalize_input(query)
        kana = romaji_to_kana(normalized) or to_hiragana(normalized)
        parameters = {
            "query": normalized,
            "kana": kana,
            "whole_word": rf"\m{re.escape(normalized)}\M",
            "limit": MAX_RESULTS,
        }
        async with self.dictionary.connect() as connection:
            rows = (await connection.execute(text(SEARCH), parameters)).all()
        words: list[dict[str, Any]] = []
        for word_id, word, reading, level, meanings in rows:
            parsed: Any = json.loads(meanings) if isinstance(meanings, str) else meanings
            words.append(
                {"word_id": word_id, "word": word, "reading": reading, "level": f"N{level}", "meanings": list(parsed)}
            )
        return words
