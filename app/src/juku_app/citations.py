"""The citation check (stub: lands in the next commit)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CitationCheck:
    is_verified: bool
    cited: tuple[str, ...]
    unknown: tuple[str, ...]


def check_citations(answer: str, tool_results: Iterable[Any]) -> CitationCheck:
    raise NotImplementedError
