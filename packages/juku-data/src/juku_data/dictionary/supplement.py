"""Juku's reviewed supplement words (ADR-003): common words in neither the JLPT lists nor OpenJLPT."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from importlib.resources import files

SUPPLEMENT_ID_PREFIX = "sup-"


@dataclass(frozen=True)
class SupplementWord:
    id: str
    word: str
    reading: str
    jmdict_id: int
    meanings: str


def read_supplement() -> list[SupplementWord]:
    """The words in juku_data/data/supplement_words.csv (lines starting with # are notes)."""
    text = (files("juku_data") / "data" / "supplement_words.csv").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    words: list[SupplementWord] = []
    for row in csv.DictReader(lines):
        word = SupplementWord(row["id"], row["word"], row["reading"], int(row["jmdict_id"]), row["meanings"])
        if word.id != f"{SUPPLEMENT_ID_PREFIX}{word.jmdict_id}":
            raise ValueError(f"supplement word {word.word}: its id must be {SUPPLEMENT_ID_PREFIX}{word.jmdict_id}")
        words.append(word)
    return words
