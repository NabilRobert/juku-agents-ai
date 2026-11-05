"""The data a page hands its Vue component (assets.json_script): it can't break out of its script tag."""

import json
import re
from datetime import date
from types import MappingProxyType

import pytest
from juku_app.assets import json_script

HOSTILE = "</script><script>alert(1)</script><!-- \u2028 & é 読む"


def body_of(tag: str) -> str:
    match = re.fullmatch(r'<script type="application/json" id="page-data">(.*)</script>', str(tag), re.S)
    assert match, tag
    return match.group(1)


def test_text_that_closes_the_script_tag_stays_inside_it() -> None:
    tag = json_script("page-data", {"nickname": HOSTILE})
    body = body_of(tag)
    assert "<" not in body and ">" not in body
    assert json.loads(body) == {"nickname": HOSTILE}


def test_japanese_is_written_as_itself() -> None:
    assert "読む" in body_of(json_script("page-data", {"word": "読む"}))


def test_database_rows_and_dates_become_json() -> None:
    # A mapping that isn't a dict, as SQLAlchemy's RowMapping is.
    row = MappingProxyType({"public_id": "abc", "created_at": date(2026, 11, 5)})
    assert json.loads(body_of(json_script("page-data", [row]))) == [{"public_id": "abc", "created_at": "2026-11-05"}]


def test_a_value_json_cant_hold_is_refused_with_what_to_do() -> None:
    with pytest.raises(TypeError, match="convert it in the route or template"):
        json_script("page-data", {"thing": object()})
