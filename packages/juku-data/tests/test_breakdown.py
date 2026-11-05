"""Sentence breakdowns (dictionary/breakdown.py): the words in a sentence, and the grammar points it may use."""

import pytest
from juku_data.dictionary.breakdown import GrammarMatcher, break_down, pattern_cores
from juku_data.dictionary.sentences import DictionaryWord, SentenceMapper

WORDS = [
    DictionaryWord("ame", ("雨",), ("あめ",)),
    DictionaryWord("furu", ("降る",), ("ふる",)),
    DictionaryWord("iru", ("いる", "居る"), ("いる",)),
    DictionaryWord("ano", ("あの",), ("あの",)),
    DictionaryWord("kata", ("方",), ("かた",)),
    DictionaryWord("sensei", ("先生",), ("せんせい",)),
    DictionaryWord("takai", ("高い",), ("たかい",)),
    DictionaryWord("oishii", ("おいしい",), ("おいしい",)),
    DictionaryWord("tokyo", ("東京",), ("とうきょう",)),
    DictionaryWord("kuru", ("来る",), ("くる",)),
]
GRAMMAR = {
    "wa": "〜は",
    "ga-subject": "〜が\uff08subject\uff09",
    "ga-but": "〜が\uff08but\uff09",
    "te-iru": "〜ている",
    "kata": "〜方",
    "desu": "〜です",
    "kara-from": "〜から\uff08from\uff09",
    "yori": "〜の方が〜より",
}


@pytest.fixture(scope="module")
def mapper() -> SentenceMapper:
    return SentenceMapper(WORDS)


def grammar_of(mapper: SentenceMapper, ja: str) -> set[str]:
    return set(break_down(mapper, GrammarMatcher(GRAMMAR.items()), ja).grammar_ids)


def test_a_patterns_sense_is_dropped_and_each_way_of_writing_it_kept() -> None:
    assert pattern_cores("〜が\uff08but\uff09") == [("が",)]
    assert pattern_cores("〜ではありません / 〜じゃない") == [("ではありません",), ("じゃない",)]
    assert pattern_cores("〜の方が〜より") == [("の方が", "より")]
    assert pattern_cores("〜(よ)うと思う") == [("うと思う",)]


def test_a_conjugated_pattern_matches_across_its_tokens(mapper: SentenceMapper) -> None:
    assert "te-iru" in grammar_of(mapper, "雨が降っています。")


def test_a_one_character_pattern_matches_only_a_particle_or_auxiliary(mapper: SentenceMapper) -> None:
    found = grammar_of(mapper, "あの方は先生です。")
    assert {"wa", "desu"} <= found
    assert "kata" not in found  # the noun 方 ("that person"), not the pattern 〜方


def test_the_subject_ga_and_the_but_ga_are_told_apart(mapper: SentenceMapper) -> None:
    assert grammar_of(mapper, "雨が降っています。") & {"ga-subject", "ga-but"} == {"ga-subject"}
    assert grammar_of(mapper, "高いですが、おいしいです。") & {"ga-subject", "ga-but"} == {"ga-but"}


def test_a_two_part_pattern_needs_both_parts(mapper: SentenceMapper) -> None:
    assert "kara-from" in grammar_of(mapper, "東京から来ました。")
    assert "yori" not in grammar_of(mapper, "東京から来ました。")


def test_each_token_says_what_it_is_and_which_word_it_stands_for(mapper: SentenceMapper) -> None:
    tokens = break_down(mapper, GrammarMatcher([]), "雨が降っています。").tokens
    shown = [(token.surface, token.kind, token.word_ids) for token in tokens]
    assert shown[:3] == [("雨", "word", ("ame",)), ("が", "grammar", ()), ("降っ", "word", ("furu",))]
    assert shown[-1] == ("。", "symbol", ())
    assert tokens[0].reading == "あめ"
