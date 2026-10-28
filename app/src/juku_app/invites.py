"""Invite codes (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine


class InviteRefusedError(Exception):
    """The code is wrong, or not one Arthur issued."""


@dataclass(frozen=True)
class Invite:
    id: int
    learner_id: int | None


async def issue_codes(engine: AsyncEngine, count: int) -> list[str]:
    raise NotImplementedError


async def redeem(engine: AsyncEngine, code: str) -> Invite:
    raise NotImplementedError


async def attach(engine: AsyncEngine, invite: Invite, learner_id: int) -> None:
    raise NotImplementedError
