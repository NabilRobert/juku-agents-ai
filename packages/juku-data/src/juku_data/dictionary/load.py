"""Load the pinned OpenJLPT build into the `dict` database (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncEngine

from juku_data.dictionary.pin import OPENJLPT_COMMIT
from juku_data.dictionary.source import SourceFiles


@dataclass(frozen=True)
class LoadReport:
    commit: str
    row_counts: dict[str, int]
    table_md5: dict[str, str]
    disappeared_ids: list[str] = field(default_factory=list[str])
    sentences_total: int = 0
    sentences_mapped: int = 0
    content_tokens: int = 0
    content_tokens_mapped: int = 0
    seconds: float = 0.0


async def load_dictionary(engine: AsyncEngine, source: SourceFiles, *, commit: str = OPENJLPT_COMMIT) -> LoadReport:
    raise NotImplementedError
