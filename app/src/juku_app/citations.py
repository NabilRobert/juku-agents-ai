"""The citation check on every chat answer (Phase 2 AG5; Phase 1 Q2).

Shiori cites each fact as `[ref:<id>]`, where the ID is one that a tool
returned in this turn: a word, a sentence, a grammar point. The app
collects every ID the turn's tool results contain and checks each cited
ID against them. An answer citing anything else, or stating facts with no
citation at all, is labelled "belum terverifikasi" on the page. The one
answer that needs no citation is the honest "tidak ada di data".
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

CITATION = re.compile(r"\[ref:([A-Za-z0-9_-]+)\]")
NOT_IN_DATA = "tidak ada di data"


@dataclass(frozen=True)
class CitationCheck:
    is_verified: bool
    cited: tuple[str, ...]
    unknown: tuple[str, ...]


def returned_ids(value: Any) -> set[str]:
    """Every value under a key named `id` or ending in `_id`, anywhere in a tool result."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in cast(dict[str, Any], value).items():
            if (key == "id" or key.endswith("_id")) and isinstance(child, str | int):
                found.add(str(child))
            found |= returned_ids(child)
    elif isinstance(value, list):
        for child in cast(list[Any], value):
            found |= returned_ids(child)
    return found


def check_citations(answer: str, tool_results: Iterable[Any]) -> CitationCheck:
    cited = tuple(CITATION.findall(answer))
    known: set[str] = set()
    for result in tool_results:
        known |= returned_ids(result)
    unknown = tuple(cited_id for cited_id in cited if cited_id not in known)
    if not cited:
        return CitationCheck(is_verified=NOT_IN_DATA in answer.lower(), cited=(), unknown=())
    return CitationCheck(is_verified=not unknown, cited=cited, unknown=unknown)
