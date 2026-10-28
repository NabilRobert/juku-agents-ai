"""Consent before first use (Phase 2, privacy): versioned, 18+, and stating the processing abroad.

The notice's text is a committed, versioned template
(templates/consent/<version>.html). Each learner's record keeps the
version they accepted and when. Changing the text means a new
CONSENT_VERSION, and learners are asked again before their next activity.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

CONSENT_VERSION = "2026-10-28"


@dataclass(frozen=True)
class ConsentAnswers:
    is_adult: bool
    accepts_service: bool
    accepts_aggregates: bool
    accepts_group_digest: bool


class ConsentRefusedError(Exception):
    """A required box wasn't ticked: 18 or older, and the service itself."""


async def record_consent(
    engine: AsyncEngine, learner_id: int, answers: ConsentAnswers, version: str = CONSENT_VERSION
) -> None:
    if not answers.is_adult:
        raise ConsentRefusedError("Juku hanya untuk usia 18 tahun ke atas.")
    if not answers.accepts_service:
        raise ConsentRefusedError("Persetujuan untuk layanan diperlukan untuk memakai Juku.")
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.consents (learner_id, version, is_adult, accepts_service, accepts_aggregates, "
                "accepts_group_digest) VALUES (:learner, :version, true, true, :aggregates, :digest)"
            ),
            {
                "learner": learner_id,
                "version": version,
                "aggregates": answers.accepts_aggregates,
                "digest": answers.accepts_group_digest,
            },
        )


async def has_current_consent(engine: AsyncEngine, learner_id: int, version: str = CONSENT_VERSION) -> bool:
    async with engine.connect() as connection:
        return bool(
            await connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM app.consents WHERE learner_id = :learner AND version = :version)"),
                {"learner": learner_id, "version": version},
            )
        )
