"""The curriculum (Arthur, 2026-11-05): N5 to N2 as numbered units, built from the dictionary when it loads.

Arthur: "is it possible to make a curriculum? ... since i picked n2 as my target. theres no structure."
Each JLPT level is cut into units of UNIT_WORDS words, in an order a learner can follow:

- **Words.** Every word of the level is in exactly one unit. Kanji words come in order of their rarest
  kanji's frequency (KANJIDIC2's rank: the most used first), and kana-only words are spread evenly
  through the level, so a unit mixes both and the first units aren't all kana.
- **Kanji.** A kanji belongs to the first unit whose words use it.
- **Grammar.** The level's grammar points, in OpenJLPT's own teaching order, spread evenly over its units.
- **Sentences.** A reading-practice sentence belongs to the first unit by which all its words have been
  taught, at most SENTENCES_PER_UNIT per unit, those using most of the unit's own words first.

It's deterministic and $0: the same build gives the same units, so a learner's place in it holds across
loads. Only N5 to N2, Juku's levels; N1 words and supplement words are in no unit, so a sentence using one
is in none either.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

UNIT_WORDS = 15
SENTENCES_PER_UNIT = 5
LEVELS = (5, 4, 3, 2)
# A kanji with no frequency rank in KANJIDIC2 is among the rarest.
UNRANKED = 9999


@dataclass(frozen=True)
class CurriculumWord:
    word_id: str
    spelling: str
    level: int


@dataclass(frozen=True)
class CurriculumSentence:
    sentence_id: int
    word_ids: frozenset[str]
    length: int


@dataclass
class Unit:
    unit_id: int  # the unit's place in the whole path, from 1
    level: int
    number: int  # its place in its level, from 1
    word_ids: list[str] = field(default_factory=list[str])
    kanji: list[str] = field(default_factory=list[str])
    grammar_ids: list[str] = field(default_factory=list[str])
    sentence_ids: list[int] = field(default_factory=list[int])


def is_kanji(character: str) -> bool:
    return "\u4e00" <= character <= "\u9fff"


def _rarest_kanji_rank(spelling: str, frequency: dict[str, int]) -> int | None:
    """The frequency rank of the spelling's rarest kanji; None for a kana-only word.

    A kanji the dictionary's kanji table doesn't list (飴, in 飴) is among the rarest, not a kana.
    """
    ranks = [frequency.get(character, UNRANKED) for character in spelling if is_kanji(character)]
    return max(ranks) if ranks else None


def _interleave(kanji_words: list[CurriculumWord], kana_words: list[CurriculumWord]) -> list[CurriculumWord]:
    """Both lists in their own order, the kana words spread evenly between the kanji words."""
    total = len(kanji_words) + len(kana_words)
    ordered: list[CurriculumWord] = []
    taken_kana = taken_kanji = 0
    for position in range(1, total + 1):
        # The next kana word is due once its share of the level is reached at this position.
        kana_due = taken_kana < len(kana_words) and (taken_kana + 1) * total <= position * len(kana_words)
        if kana_due or taken_kanji == len(kanji_words):
            ordered.append(kana_words[taken_kana])
            taken_kana += 1
        else:
            ordered.append(kanji_words[taken_kanji])
            taken_kanji += 1
    return ordered


def order_level(words: Iterable[CurriculumWord], frequency: dict[str, int]) -> list[CurriculumWord]:
    with_kanji: list[tuple[int, str, CurriculumWord]] = []
    kana_only: list[CurriculumWord] = []
    for word in words:
        rank = _rarest_kanji_rank(word.spelling, frequency)
        if rank is None:
            kana_only.append(word)
        else:
            with_kanji.append((rank, word.word_id, word))
    kana_only.sort(key=lambda word: (len(word.spelling), word.word_id))
    return _interleave([word for _, _, word in sorted(with_kanji)], kana_only)


def _split(items: Sequence[str], parts: int) -> list[list[str]]:
    """`items` in order, in `parts` runs as even as the count allows."""
    return [list(items[part * len(items) // parts : (part + 1) * len(items) // parts]) for part in range(parts)]


def _units_of_level(
    level: int, words: list[CurriculumWord], grammar_ids: Sequence[str], first_unit_id: int, kanji_seen: set[str]
) -> list[Unit]:
    count = -(-len(words) // UNIT_WORDS)  # ceiling: every word in a unit, and no unit without words
    if count == 0:
        return []
    grammar_runs = _split(grammar_ids, count)
    units: list[Unit] = []
    for number in range(1, count + 1):
        unit_words = words[(number - 1) * UNIT_WORDS : number * UNIT_WORDS]
        new_kanji: list[str] = []
        for word in unit_words:
            for character in word.spelling:
                if is_kanji(character) and character not in kanji_seen:
                    kanji_seen.add(character)
                    new_kanji.append(character)
        units.append(
            Unit(
                unit_id=first_unit_id + number - 1,
                level=level,
                number=number,
                word_ids=[word.word_id for word in unit_words],
                kanji=new_kanji,
                grammar_ids=grammar_runs[number - 1],
            )
        )
    return units


def _place_sentences(units: list[Unit], sentences: Iterable[CurriculumSentence]) -> None:
    """Each sentence to the first unit by which all its words are taught, the best SENTENCES_PER_UNIT kept."""
    unit_of_word = {word_id: unit.unit_id for unit in units for word_id in unit.word_ids}
    by_unit: dict[int, list[tuple[int, int, int]]] = {}
    for sentence in sentences:
        if not sentence.word_ids or not sentence.word_ids <= unit_of_word.keys():
            continue
        unit_id = max(unit_of_word[word_id] for word_id in sentence.word_ids)
        unit_words = sum(1 for word_id in sentence.word_ids if unit_of_word[word_id] == unit_id)
        by_unit.setdefault(unit_id, []).append((-unit_words, sentence.length, sentence.sentence_id))
    for unit in units:
        best = sorted(by_unit.get(unit.unit_id, []))[:SENTENCES_PER_UNIT]
        unit.sentence_ids = [sentence_id for _, _, sentence_id in best]


def build_curriculum(
    words: Iterable[CurriculumWord],
    frequency: dict[str, int],
    grammar_order: Sequence[tuple[str, int]],
    sentences: Iterable[CurriculumSentence],
) -> list[Unit]:
    """The whole path, N5 to N2, numbered from 1. `grammar_order` is (grammar ID, level) in teaching order."""
    by_level: dict[int, list[CurriculumWord]] = {level: [] for level in LEVELS}
    for word in words:
        if word.level in by_level:
            by_level[word.level].append(word)
    units: list[Unit] = []
    kanji_seen: set[str] = set()
    for level in LEVELS:
        grammar_ids = [grammar_id for grammar_id, grammar_level in grammar_order if grammar_level == level]
        ordered = order_level(by_level[level], frequency)
        units += _units_of_level(level, ordered, grammar_ids, len(units) + 1, kanji_seen)
    _place_sentences(units, sentences)
    return units
