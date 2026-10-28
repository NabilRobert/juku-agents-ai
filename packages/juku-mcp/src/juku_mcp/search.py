"""search_words (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class DictionarySearch:
    dictionary: AsyncEngine

    async def search(self, query: str) -> list[dict[str, object]]:
        raise NotImplementedError
