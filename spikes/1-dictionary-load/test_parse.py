"""The COPY encoding and the index-token grammar, where a slip would load
wrong rows silently."""

from parse import INDEX_TOKEN, cell


def test_null_and_empty_list_are_null() -> None:
    assert cell(None) == r"\N"
    assert cell([]) == r"\N"


def test_list_is_a_quoted_array_literal() -> None:
    assert cell(["v5r", "vt"]) == '{"v5r","vt"}'
    # A quote inside an element is escaped for the array, then the backslash for COPY.
    assert cell(['a"b']) == '{"a\\\\"b"}'


def test_tabs_newlines_and_backslashes_are_escaped() -> None:
    assert cell("a\tb\nc\\d") == "a\\tb\\nc\\\\d"


def test_booleans() -> None:
    assert cell(True) == "t"
    assert cell(False) == "f"


def test_index_token_parts() -> None:
    m = INDEX_TOKEN.match("為る(する)[01]{した}~")
    assert m is not None
    assert m.groups() == ("為る", "する", "01", "した", "~")
    m = INDEX_TOKEN.match("は")
    assert m is not None
    assert m.groups() == ("は", None, None, None, None)
    assert INDEX_TOKEN.match("か如何か{かどうか}{かどう}") is None
