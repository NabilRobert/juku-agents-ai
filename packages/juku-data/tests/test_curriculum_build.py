"""The curriculum's path (dictionary/curriculum.py): units a learner can follow, built the same way each time."""

from juku_data.dictionary.curriculum import (
    SENTENCES_PER_UNIT,
    UNIT_WORDS,
    CurriculumSentence,
    CurriculumWord,
    build_curriculum,
    order_level,
)

FREQUENCY = {"一": 2, "人": 5, "大": 7, "飲": 900, "日": 1}


def word(word_id: str, spelling: str, level: int = 5) -> CurriculumWord:
    return CurriculumWord(word_id=word_id, spelling=spelling, level=level)


def test_kanji_words_come_in_order_of_their_rarest_kanji() -> None:
    ordered = order_level([word("a", "飲む"), word("b", "一人"), word("c", "大人")], FREQUENCY)
    assert [item.word_id for item in ordered] == ["b", "c", "a"]


def test_a_kanji_missing_from_the_kanji_table_counts_as_rarest() -> None:
    ordered = order_level([word("rare", "飴"), word("common", "一つ")], FREQUENCY)
    assert [item.word_id for item in ordered] == ["common", "rare"]


def test_kana_words_are_spread_through_the_level_not_bunched_first() -> None:
    kanji_words = [word(f"k{index}", "一" * (index + 1)) for index in range(20)]
    kana_words = [word(f"h{index}", "あ" * (index + 1)) for index in range(10)]
    ordered = [item.word_id[0] for item in order_level(kanji_words + kana_words, FREQUENCY)]
    first_third, last_third = ordered[:10], ordered[20:]
    assert 2 <= first_third.count("h") <= 4 and 2 <= last_third.count("h") <= 4


def test_every_word_of_juku_levels_is_in_exactly_one_unit_and_n1_in_none() -> None:
    words = [word(f"w{index}", "一", level=5) for index in range(UNIT_WORDS * 2 + 1)] + [word("n1", "一", level=1)]
    units = build_curriculum(words, FREQUENCY, [], [])
    placed = [word_id for unit in units for word_id in unit.word_ids]
    assert sorted(placed) == sorted(f"w{index}" for index in range(UNIT_WORDS * 2 + 1))
    assert [len(unit.word_ids) for unit in units] == [UNIT_WORDS, UNIT_WORDS, 1]
    assert [(unit.unit_id, unit.level, unit.number) for unit in units] == [(1, 5, 1), (2, 5, 2), (3, 5, 3)]


def test_levels_follow_each_other_n5_first_and_grammar_spreads_in_teaching_order() -> None:
    words = [word("n4", "大人", level=4), word("n5", "一人", level=5)]
    grammar = [("wa", 5), ("ga", 5), ("te-iru", 4)]
    units = build_curriculum(words, FREQUENCY, grammar, [])
    assert [(unit.level, unit.word_ids, unit.grammar_ids) for unit in units] == [
        (5, ["n5"], ["wa", "ga"]),
        (4, ["n4"], ["te-iru"]),
    ]


def test_a_kanji_belongs_to_the_first_unit_whose_words_use_it() -> None:
    # 飲 is the rarest, so 飲日 comes last, in the second unit; 日 is new there, 人 isn't.
    words = [word(f"w{index:02}", "一人") for index in range(UNIT_WORDS)] + [word("last", "飲日人")]
    first, second = build_curriculum(words, FREQUENCY, [], [])
    assert first.kanji == ["一", "人"] and second.kanji == ["飲", "日"]


def test_a_sentence_goes_to_the_first_unit_that_has_taught_all_its_words() -> None:
    words = [word(f"w{index:02}", "一") for index in range(UNIT_WORDS * 2)]  # same kanji: in ID order
    early = CurriculumSentence(1, frozenset({"w00", "w01"}), 5)
    late = CurriculumSentence(2, frozenset({"w00", f"w{UNIT_WORDS:02}"}), 5)
    untaught = CurriculumSentence(3, frozenset({"w00", "not-in-any-unit"}), 5)
    first, second = build_curriculum(words, FREQUENCY, [], [early, late, untaught])
    assert first.sentence_ids == [1] and second.sentence_ids == [2]


def test_a_unit_keeps_the_sentences_using_most_of_its_own_words() -> None:
    words = [word(f"w{index}", "一") for index in range(UNIT_WORDS)]
    sentences = [CurriculumSentence(index, frozenset({f"w{n}" for n in range(index)}), 10) for index in range(1, 9)]
    [unit] = build_curriculum(words, FREQUENCY, [], sentences)
    assert unit.sentence_ids == [8, 7, 6, 5, 4][:SENTENCES_PER_UNIT]
