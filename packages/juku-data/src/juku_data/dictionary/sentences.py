"""The reading-practice index (Phase 2 LE4): example sentences mapped to word IDs.

Each distinct example sentence is tokenized with SudachiPy, and each
content word is matched to one dictionary word (OpenJLPT or the
supplement). A sentence is kept only if every content word maps to
exactly one ID; reading practice then offers the sentences in which a
learner knows every word but one.

What counts as a content word (Phase 2 LE4, spike 4):
- particles, auxiliaries, symbols and affixes are grammar, not words;
- names (固有名詞) and numbers (数詞) count as known;
- ない and its forms count as grammar (OpenJLPT teaches it as a pattern).
OpenJLPT's other grammar patterns are particles and auxiliaries, which the
part-of-speech rule already skips.

The matching rules are spike 4's (`resolve` in completeness.py at 17abe92),
rewritten: match the dictionary form, then the normalized form, then (for
kana) the reading; if several words share it, prefer those whose reading
matches; if nothing matches, try splitting a compound into its short units.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

import jaconv
from sudachipy import Dictionary, Morpheme, SplitMode, Tokenizer

FUNCTION_POS = frozenset({"助詞", "助動詞", "補助記号", "記号", "空白", "接尾辞", "接頭辞"})
ALWAYS_KNOWN_POS = frozenset({"固有名詞", "数詞"})
GRAMMAR_FORMS = frozenset({"ない", "なく", "なかっ", "なけれ"})
KANA_EXTRAS = frozenset("ー・ゝゞ")


@dataclass(frozen=True)
class DictionaryWord:
    """What matching needs from a word: its ID, spellings and readings."""

    id: str
    spellings: tuple[str, ...]
    readings: tuple[str, ...]


@dataclass(frozen=True)
class SourceSentence:
    ja: str
    furigana: str | None
    en: str | None
    tatoeba_id: int | None


@dataclass(frozen=True)
class MappedSentence:
    sentence_id: int
    source: SourceSentence
    word_ids: frozenset[str]


@dataclass
class ReadingIndex:
    sentences: list[MappedSentence] = field(default_factory=list[MappedSentence])
    sentences_total: int = 0
    content_tokens: int = 0
    content_tokens_mapped: int = 0


def is_kana(text: str) -> bool:
    return all("ぁ" <= char <= "ゖ" or "ァ" <= char <= "ヺ" or char in KANA_EXTRAS for char in text)


def is_function_word(morpheme: Morpheme) -> bool:
    part_of_speech = morpheme.part_of_speech()
    return (
        part_of_speech[0] in FUNCTION_POS
        or part_of_speech[1] in ALWAYS_KNOWN_POS
        or morpheme.surface() in GRAMMAR_FORMS
    )


class WordMatcher:
    """Maps a SudachiPy morpheme to the dictionary words it could be."""

    def __init__(self, words: Iterable[DictionaryWord], tokenizer: Tokenizer) -> None:
        self._by_spelling: dict[str, set[str]] = defaultdict(set)
        self._by_reading: dict[str, set[str]] = defaultdict(set)
        self._readings_of: dict[str, set[str]] = {}
        for word in words:
            self._readings_of[word.id] = set(word.readings)
            for spelling in word.spellings:
                self._by_spelling[spelling].add(word.id)
            for reading in word.readings:
                self._by_reading[reading].add(word.id)
        self._tokenizer = tokenizer
        self._reading_cache: dict[str, str] = {}

    def _reading_in_hiragana(self, form: str) -> str:
        if form not in self._reading_cache:
            readings = (morpheme.reading_form() for morpheme in self._tokenizer.tokenize(form))
            self._reading_cache[form] = "".join(jaconv.kata2hira(reading) for reading in readings)
        return self._reading_cache[form]

    def candidates(self, morpheme: Morpheme) -> set[str]:
        """The word IDs this morpheme matches; empty if none."""
        dictionary_form, normalized_form = morpheme.dictionary_form(), morpheme.normalized_form()
        by_reading = self._by_reading.get(dictionary_form) if is_kana(dictionary_form) else None
        for ids in (self._by_spelling.get(dictionary_form), self._by_spelling.get(normalized_form), by_reading):
            if not ids:
                continue
            if len(ids) == 1:
                return set(ids)
            reading = self._reading_in_hiragana(dictionary_form)
            return {word_id for word_id in ids if reading in self._readings_of[word_id]} or set(ids)
        return set()


class SentenceMapper:
    """Maps whole sentences, counting how many content tokens found exactly one word."""

    def __init__(self, words: Iterable[DictionaryWord]) -> None:
        dictionary = Dictionary(dict="core")
        self._whole_words = dictionary.tokenizer(mode=SplitMode.C)
        self._short_units = dictionary.tokenizer(mode=SplitMode.A)
        self._matcher = WordMatcher(words, self._whole_words)

    def _match_by_short_units(self, morpheme: Morpheme) -> set[str] | None:
        """A compound the dictionary lacks, matched unit by unit; None unless every unit is one word."""
        units = [unit for unit in self._short_units.tokenize(morpheme.surface()) if not is_function_word(unit)]
        if not units or (len(units) == 1 and units[0].surface() == morpheme.surface()):
            return None
        matched: set[str] = set()
        for unit in units:
            ids = self._matcher.candidates(unit)
            if len(ids) != 1:
                return None
            matched |= ids
        return matched

    def map_sentence(self, ja: str, index: ReadingIndex) -> frozenset[str] | None:
        """The sentence's word IDs if every content word maps to one; otherwise None."""
        word_ids: set[str] = set()
        is_complete = True
        for morpheme in self._whole_words.tokenize(ja):
            if is_function_word(morpheme):
                continue
            index.content_tokens += 1
            ids = self._matcher.candidates(morpheme)
            if not ids:
                ids = self._match_by_short_units(morpheme) or set()
                if ids:
                    index.content_tokens_mapped += 1
                    word_ids |= ids
                    continue
            if len(ids) == 1:
                index.content_tokens_mapped += 1
                word_ids |= ids
            else:
                is_complete = False
        return frozenset(word_ids) if is_complete and word_ids else None


def build_reading_index(words: Iterable[DictionaryWord], sentences: Iterable[SourceSentence]) -> ReadingIndex:
    """Map each distinct sentence; keep the ones that map completely, numbered from 1 in input order."""
    mapper = SentenceMapper(words)
    index = ReadingIndex()
    seen: set[str] = set()
    for source in sentences:
        if source.ja in seen:
            continue
        seen.add(source.ja)
        index.sentences_total += 1
        word_ids = mapper.map_sentence(source.ja, index)
        if word_ids is not None:
            index.sentences.append(MappedSentence(index.sentences_total, source, word_ids))
    return index
