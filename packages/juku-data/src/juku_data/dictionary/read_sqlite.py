"""Read OpenJLPT's SQLite file into rows ready for Postgres's COPY.

The file is opened read-only. JSON columns stay JSON text (Postgres stores
them as jsonb), levels become numbers (N5 = 5 ... N1 = 1, OpenJLPT's own
order, so "easier" is "larger"), and each word's example sentences are
also unnested into their own rows, since Juku looks them up by word.

The column order matches spike 1's tables exactly, so a fresh load can be
checked against spike 1's recorded md5 of every table.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

LEVEL_NUMBERS = {"N5": 5, "N4": 4, "N3": 3, "N2": 2, "N1": 1}

Row = tuple[Any, ...]


@dataclass(frozen=True)
class OpenJlptRows:
    vocab: list[Row]
    vocab_example: list[Row]
    kanji: list[Row]
    grammar: list[Row]
    pos: list[Row]

    def counts(self) -> dict[str, int]:
        return {
            "vocab": len(self.vocab),
            "vocab_example": len(self.vocab_example),
            "kanji": len(self.kanji),
            "grammar": len(self.grammar),
            "pos": len(self.pos),
        }


def level_number(level: str) -> int:
    try:
        return LEVEL_NUMBERS[level]
    except KeyError:
        raise ValueError(f"unknown JLPT level {level!r}: OpenJLPT's levels are N5 to N1") from None


def _examples(vocab_id: str, examples_json: str) -> list[Row]:
    examples = cast(list[dict[str, Any]], json.loads(examples_json))
    return [
        (vocab_id, order, example.get("ja"), example.get("furigana"), example.get("en"), example.get("tatoeba_id"))
        for order, example in enumerate(examples, start=1)
    ]


def read_openjlpt(sqlite_path: Path) -> OpenJlptRows:
    connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        vocab_source = connection.execute(
            "SELECT id, word, reading, romaji, meanings, level, pos, jmdict_id, other_forms, other_readings, examples "
            "FROM vocab ORDER BY id"
        ).fetchall()
        vocab = [(*row[:5], level_number(row[5]), *row[6:]) for row in vocab_source]
        vocab_example = [example for row in vocab_source for example in _examples(row[0], row[10])]
        kanji = [
            (row[0], level_number(row[1]), *row[2:12], bool(row[12]))
            for row in connection.execute(
                "SELECT character, level, strokes, grade, freq, radical, radical_number, onyomi, kunyomi, nanori, "
                "meanings, words, supplementary FROM kanji ORDER BY character"
            )
        ]
        grammar = [
            (*row[:4], level_number(row[4]), *row[5:])
            for row in connection.execute(
                "SELECT id, pattern, reading, romaji, level, meaning, formation, examples, tags, notes "
                "FROM grammar ORDER BY id"
            )
        ]
        pos = connection.execute("SELECT code, description FROM pos ORDER BY code").fetchall()
    finally:
        connection.close()
    return OpenJlptRows(vocab=vocab, vocab_example=vocab_example, kanji=kanji, grammar=grammar, pos=pos)
