"""JI1: what a learner types is normalized before any lookup (standard checks, "Japanese input")."""

import pytest
from juku_data.japanese import normalize_input, romaji_to_kana, to_hiragana


@pytest.mark.parametrize(
    ("typed", "normalized"),
    [
        ("taberu", "taberu"),
        ("TABERU", "taberu"),  # upper case folded
        ("ｔａｂｅｒｕ", "taberu"),  # full-width romaji
        ("ﾀﾍﾞﾙ", "タベル"),  # half-width katakana becomes full-width; katakana stays katakana
        ("ｶﾞｯｺｳ", "ガッコウ"),  # half-width, with voicing marks
        ("食べる", "食べる"),
        ("  たべる　", "たべる"),  # spaces, the ideographic one too
        ("１２３", "123"),  # full-width digits
        ("To  Eat", "to eat"),  # English stays English; runs of spaces collapse
    ],
)
def test_input_is_normalized(typed: str, normalized: str) -> None:
    assert normalize_input(typed) == normalized


@pytest.mark.parametrize(
    ("typed", "kana"),
    [
        ("taberu", "たべる"),
        ("gakkou", "がっこう"),  # double consonant
        ("kyou", "きょう"),  # contracted sound
        ("tabeる", "たべる"),  # mixed romaji and kana
        ("TABERU", "たべる"),
        ("eat", None),  # English: a letter would be left over
        ("to eat", None),
        ("食べる", None),  # nothing to convert
    ],
)
def test_romaji_becomes_kana_only_when_all_of_it_converts(typed: str, kana: str | None) -> None:
    assert romaji_to_kana(typed) == kana


@pytest.mark.parametrize(("text", "hiragana"), [("タベル", "たべる"), ("たべる", "たべる"), ("コーヒー", "こーひー")])
def test_katakana_becomes_hiragana_for_reading_comparisons(text: str, hiragana: str) -> None:
    assert to_hiragana(text) == hiragana
