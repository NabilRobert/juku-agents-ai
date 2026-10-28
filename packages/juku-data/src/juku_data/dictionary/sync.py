"""Mirror the dictionary's index columns into the app database (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class SyncReport:
    words: int
    word_kanji: int
    kanji: int
    leverage_rows: int
    items_missing_from_dictionary: list[str] = field(default_factory=list[str])


async def sync_index(dict_engine: AsyncEngine, app_engine: AsyncEngine) -> SyncReport:
    raise NotImplementedError
