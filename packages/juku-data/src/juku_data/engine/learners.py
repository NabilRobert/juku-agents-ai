"""The engine's learners: creating, finding, locking and changing them.

Every write in the engine starts from `lock_learner`, so two tabs answering
at once can't interleave their updates (engine/writes.py).
"""

from __future__ import annotations

import secrets
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncConnection

from juku_data.engine.models import Learner
from juku_data.engine.recompute import rebuild_learners

# Juku serves N5 to N2 (Phase 2, core scenario); OpenJLPT numbers them 5 to 2.
EASIEST_LEVEL, HARDEST_TARGET_LEVEL = 5, 2
# 12 random bytes: 16 URL-safe characters, never guessable from the internal ID.
PUBLIC_ID_BYTES = 12


class LearnerNotFoundError(LookupError):
    """No learner has this ID."""


def check_target_level(target_level: int) -> None:
    if not HARDEST_TARGET_LEVEL <= target_level <= EASIEST_LEVEL:
        raise ValueError(f"target level {target_level} is outside N5 to N2: use 5 (N5) to 2 (N2)")


def check_timezone(timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown timezone {timezone!r}: use an IANA name such as Asia/Jakarta") from None


LEARNER_FIELDS = ("id", "public_id", "cohort_id", "target_level", "timezone", "exam_date")
LEARNER_COLUMNS = ", ".join(LEARNER_FIELDS)


def _learner(row: Row[Any]) -> Learner:
    return Learner.model_validate(dict(zip(LEARNER_FIELDS, row, strict=True)))


async def _select_learner(connection: AsyncConnection, learner_id: int, *, lock: bool) -> Learner:
    lock_clause = " FOR UPDATE" if lock else ""
    row = (
        await connection.execute(
            text(f"SELECT {LEARNER_COLUMNS} FROM learning.learners WHERE id = :id{lock_clause}"),  # noqa: S608
            {"id": learner_id},
        )
    ).first()
    if row is None:
        raise LearnerNotFoundError(f"no learner with ID {learner_id}")
    return _learner(row)


async def load_learner(connection: AsyncConnection, learner_id: int) -> Learner:
    return await _select_learner(connection, learner_id, lock=False)


async def lock_learner(connection: AsyncConnection, learner_id: int) -> Learner:
    """The learner, with their row locked until the transaction ends: one writer per learner at a time."""
    return await _select_learner(connection, learner_id, lock=True)


async def find_learner(connection: AsyncConnection, public_id: str) -> Learner:
    row = (
        await connection.execute(
            text(f"SELECT {LEARNER_COLUMNS} FROM learning.learners WHERE public_id = :public_id"),  # noqa: S608
            {"public_id": public_id},
        )
    ).first()
    if row is None:
        raise LearnerNotFoundError(f"no learner with public ID {public_id!r}")
    return _learner(row)


async def create_learner(  # noqa: PLR0913 (keyword-only: the learner's own fields)
    connection: AsyncConnection,
    *,
    nickname: str,
    target_level: int,
    timezone: str,
    exam_date: date | None,
    cohort_id: int,
    public_id: str | None,
) -> Learner:
    check_target_level(target_level)
    check_timezone(timezone)
    row = (
        await connection.execute(
            text(
                "INSERT INTO learning.learners (public_id, cohort_id, nickname, target_level, exam_date, timezone) "
                "VALUES (:public_id, :cohort_id, :nickname, :target_level, :exam_date, :timezone) "
                "RETURNING id, public_id, cohort_id, target_level, timezone, exam_date"
            ),
            {
                "public_id": public_id or secrets.token_urlsafe(PUBLIC_ID_BYTES),
                "cohort_id": cohort_id,
                "nickname": nickname,
                "target_level": target_level,
                "exam_date": exam_date,
                "timezone": timezone,
            },
        )
    ).one()
    learner = _learner(row)
    # No events yet, so the rebuild gives five empty coverage rows and the starting candidates.
    await rebuild_learners(connection, [learner.id])
    return learner


async def update_learner(
    connection: AsyncConnection, learner_id: int, *, target_level: int | None = None, timezone: str | None = None
) -> None:
    """A new level changes the candidates; a new timezone changes which day each answer fell on. Both rebuild."""
    await lock_learner(connection, learner_id)
    if target_level is not None:
        check_target_level(target_level)
        await connection.execute(
            text("UPDATE learning.learners SET target_level = :level WHERE id = :id"),
            {"level": target_level, "id": learner_id},
        )
    if timezone is not None:
        check_timezone(timezone)
        await connection.execute(
            text("UPDATE learning.learners SET timezone = :zone WHERE id = :id"), {"zone": timezone, "id": learner_id}
        )
    await rebuild_learners(connection, [learner_id])
