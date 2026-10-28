"""A synthetic database of 5,000 learners, for fitness function FF1 (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

SYNTHETIC_LEARNERS = 5000
HEAVY_LEARNER_PUBLIC_ID = "syn-heavy"
HEAVY_LEARNER_KNOWN_WORDS = 4000


@dataclass(frozen=True)
class SyntheticReport:
    learners: int
    events: int
    seconds: float


async def build_synthetic(app: AsyncEngine, *, learners: int = SYNTHETIC_LEARNERS) -> SyntheticReport:
    raise NotImplementedError
