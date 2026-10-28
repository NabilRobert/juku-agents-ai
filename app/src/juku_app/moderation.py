"""The moderation check before the model sees a message (AG6) (stub: lands with the chat)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Verdict:
    suggests_self_harm: bool


class Moderator(Protocol):
    async def check(self, message: str) -> Verdict: ...
