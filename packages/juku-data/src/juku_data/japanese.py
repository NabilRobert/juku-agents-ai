"""Japanese input normalization (Phase 2 JI1, scale path gap 4).

Learners type romaji, full-width or half-width forms and mixed scripts.
Everything they type is folded first (width, case, spaces), so lookups
compare like with like. Romaji becomes kana only when all of it converts,
so English ("to eat") reaches the English search untouched. Reuses jaconv
for the kana tables rather than hand-written ones (ADR-025).
"""

from __future__ import annotations

import re
import unicodedata

import jaconv

ASCII_LETTER = re.compile(r"[a-z]")
# Romaji ends in a vowel, n, or a long-vowel mark. jaconv turns a dangling
# consonant into a small っ ("eat" -> えあっ), so a word ending in one isn't romaji.
DANGLING_CONSONANT = re.compile(r"[b-df-hj-mp-tv-z]$")
SPACES = re.compile(r"\s+")


def normalize_input(text: str) -> str:
    """NFKC (full-width letters and digits to ASCII, half-width kana to full-width), lower case, single spaces."""
    folded = unicodedata.normalize("NFKC", text).lower()
    return SPACES.sub(" ", folded).strip()


def romaji_to_kana(text: str) -> str | None:
    """Hiragana, if `text` is romaji (possibly mixed with kana) that converts with no letter left over."""
    normalized = normalize_input(text)
    if not ASCII_LETTER.search(normalized) or DANGLING_CONSONANT.search(normalized):
        return None
    converted = jaconv.alphabet2kana(normalized)
    if ASCII_LETTER.search(converted) or " " in converted:
        return None
    return converted


def to_hiragana(text: str) -> str:
    """Katakana to hiragana, for comparing readings."""
    return jaconv.kata2hira(text)
