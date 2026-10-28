"""Consent (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

CONSENT_VERSION = "2026-10-28"


@dataclass(frozen=True)
class ConsentAnswers:
    is_adult: bool
    accepts_service: bool
    accepts_aggregates: bool
    accepts_group_digest: bool


class ConsentRefusedError(Exception):
    """A required box wasn't ticked."""


async def record_consent(engine: AsyncEngine, learner_id: int, answers: ConsentAnswers) -> None:
    raise NotImplementedError


async def has_current_consent(engine: AsyncEngine, learner_id: int, version: str = CONSENT_VERSION) -> bool:
    raise NotImplementedError
