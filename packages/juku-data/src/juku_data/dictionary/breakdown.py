"""Sentence breakdowns: each example sentence split into its words and the grammar points it may use.

Built once, when the dictionary loads (load.py), because SudachiPy's dictionary is too large to load in the
web app. The app only reads the stored rows (`sentence_breakdown`).

A token is a word (with the dictionary words it stands for, found as the reading index finds them), a piece
of grammar (particles, auxiliaries, ない), a name, a number or punctuation.

Grammar points are found by their pattern's kana "core": OpenJLPT's `〜ている` is the core ている, matched when
whole consecutive tokens spell it, the last one in its surface or dictionary form (て + いる). A core of one
particle or auxiliary only matches a token tagged as one, so the は inside a word never counts. Senses that
share a core (に for time, place, destination...) all match: the page lists them, it doesn't guess.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import jaconv
from sudachipy import Morpheme

from juku_data.dictionary.sentences import ALWAYS_KNOWN_POS, SentenceMapper, is_function_word

SYMBOL_POS = frozenset({"補助記号", "記号", "空白"})
GRAMMAR_POS = frozenset({"助詞", "助動詞"})
# OpenJLPT writes a sense in full-width brackets and an optional part in half-width ones:
# 〜が, then (but) in full-width brackets; 〜(よ)うと思う.
OPEN, CLOSE = "\uff08", "\uff09"
SENSE_OR_OPTIONAL = re.compile(rf"{OPEN}[^{CLOSE}]*{CLOSE}|\([^)]*\)")
JAPANESE_ONLY = re.compile(r"^[\u3040-\u30ff\u4e00-\u9fff\u3005\u30fc]+$")
# Senses of one particle that SudachiPy tells apart by its subtype; the others list every sense.
PARTICLE_SENSES = {
    f"〜が{OPEN}subject{CLOSE}": "格助詞",
    f"〜が{OPEN}but{CLOSE}": "接続助詞",
    f"〜から{OPEN}from{CLOSE}": "格助詞",
    f"〜から{OPEN}reason{CLOSE}": "接続助詞",
    f"〜か{OPEN}question{CLOSE}": "終助詞",
    f"〜か{OPEN}or{CLOSE}": "副助詞",
    f"〜か{OPEN}embedded question{CLOSE}": "副助詞",
}


@dataclass(frozen=True)
class Token:
    surface: str
    reading: str
    kind: str  # "word", "grammar", "name", "number" or "symbol"
    word_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Breakdown:
    ja: str
    tokens: tuple[Token, ...]
    grammar_ids: tuple[str, ...]


def pattern_cores(pattern: str) -> list[tuple[str, ...]]:
    """The ways a pattern can be written, each as the kana segments that must appear in order.

    `〜の方が〜より` is one way with two segments; `〜ない / 〜じゃない` is two ways. Patterns with nothing
    Japanese left to match (only a sense, say) give none.
    """
    ways: list[tuple[str, ...]] = []
    for way in SENSE_OR_OPTIONAL.sub("", pattern).split("/"):
        segments = tuple(segment.strip() for segment in way.split("〜") if segment.strip())
        if segments and all(JAPANESE_ONLY.match(segment) for segment in segments):
            ways.append(segments)
    return ways


def _kind(morpheme: Morpheme) -> str:
    part_of_speech = morpheme.part_of_speech()
    if part_of_speech[0] in SYMBOL_POS:
        return "symbol"
    if part_of_speech[1] == "数詞":
        return "number"
    if part_of_speech[1] in ALWAYS_KNOWN_POS:
        return "name"
    return "grammar" if is_function_word(morpheme) else "word"


def _spells_at(morphemes: Sequence[Morpheme], start: int, segment: str, subtype: str | None) -> int | None:
    """The index after the tokens from `start` that spell `segment` exactly, or None.

    `subtype`, if given, is the particle subtype a one-token match must have (PARTICLE_SENSES).
    """
    spelled = ""
    for end in range(start, len(morphemes)):
        morpheme = morphemes[end]
        if spelled + morpheme.dictionary_form() == segment or spelled + morpheme.surface() == segment:
            is_one_character = end == start and len(segment) == 1
            is_grammar_token = morpheme.part_of_speech()[0] in GRAMMAR_POS
            # A one-character core must be a particle or auxiliary: the noun 方 isn't the pattern 〜方.
            if is_one_character and not is_grammar_token:
                return None
            if subtype and end == start and morpheme.part_of_speech()[1] != subtype:
                return None
            return end + 1
        spelled += morpheme.surface()
        if not segment.startswith(spelled):
            return None
    return None


def _uses(morphemes: Sequence[Morpheme], segments: tuple[str, ...], subtype: str | None) -> bool:
    """Whether the segments appear in order, each spelled by whole tokens."""
    position = 0
    for segment in segments:
        found = None
        for start in range(position, len(morphemes)):
            found = _spells_at(morphemes, start, segment, subtype)
            if found is not None:
                break
        if found is None:
            return False
        position = found
    return True


class GrammarMatcher:
    """Which of OpenJLPT's grammar points a tokenized sentence may use."""

    def __init__(self, grammar: Iterable[tuple[str, str]]) -> None:
        self._ways = [
            (grammar_id, pattern_cores(pattern), PARTICLE_SENSES.get(pattern)) for grammar_id, pattern in grammar
        ]

    def matches(self, morphemes: Sequence[Morpheme]) -> tuple[str, ...]:
        found: list[str] = []
        for grammar_id, ways, subtype in self._ways:
            if any(_uses(morphemes, segments, subtype) for segments in ways):
                found.append(grammar_id)
        return tuple(found)


def break_down(mapper: SentenceMapper, grammar: GrammarMatcher, ja: str) -> Breakdown:
    morphemes = mapper.tokenize(ja)
    tokens = tuple(
        Token(
            surface=morpheme.surface(),
            reading=jaconv.kata2hira(morpheme.reading_form()),
            kind=(kind := _kind(morpheme)),
            word_ids=tuple(sorted(mapper.word_ids(morpheme))) if kind == "word" else (),
        )
        for morpheme in morphemes
    )
    return Breakdown(ja=ja, tokens=tokens, grammar_ids=grammar.matches(morphemes))


def build_breakdowns(mapper: SentenceMapper, grammar: GrammarMatcher, sentences: Iterable[str]) -> list[Breakdown]:
    """One breakdown per distinct sentence, in the order first seen."""
    return [break_down(mapper, grammar, ja) for ja in dict.fromkeys(sentences)]
