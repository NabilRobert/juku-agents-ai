"""Invite codes (ADR-013): one random code per person, issued by Arthur; only its hash is kept.

A code reads `<lookup>.<secret>`. The lookup part finds the row; the
secret is checked against its Argon2 hash (argon2-cffi), so the table
alone logs no one in. The first time a code is used, it's attached to the
learner it creates; after that, the code is that learner's login.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# 6 bytes of lookup and 15 of secret: short enough to type, 120 bits that can't be guessed.
LOOKUP_BYTES = 6
SECRET_BYTES = 15
hasher = PasswordHasher()


class InviteRefusedError(Exception):
    """The code is wrong, or not one Arthur issued."""


@dataclass(frozen=True)
class Invite:
    id: int
    learner_id: int | None


async def issue_codes(engine: AsyncEngine, count: int) -> list[str]:
    """Make `count` codes; return them once. Only their hashes are stored."""
    codes: list[str] = []
    async with engine.begin() as connection:
        for _ in range(count):
            lookup, secret = secrets.token_urlsafe(LOOKUP_BYTES), secrets.token_urlsafe(SECRET_BYTES)
            await connection.execute(
                text("INSERT INTO app.invite_codes (lookup, secret_hash) VALUES (:lookup, :hash)"),
                {"lookup": lookup, "hash": hasher.hash(secret)},
            )
            codes.append(f"{lookup}.{secret}")
    return codes


async def redeem(engine: AsyncEngine, code: str) -> Invite:
    """The invite this code belongs to, or InviteRefusedError."""
    lookup, _, secret = code.strip().partition(".")
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text("SELECT id, secret_hash, learner_id FROM app.invite_codes WHERE lookup = :lookup"),
                {"lookup": lookup},
            )
        ).first()
    if row is None or not secret:
        raise InviteRefusedError("that code isn't one of Juku's")
    try:
        hasher.verify(str(row.secret_hash), secret)
    except VerificationError:
        raise InviteRefusedError("that code isn't one of Juku's") from None
    return Invite(id=int(row.id), learner_id=row.learner_id)


async def attach(engine: AsyncEngine, invite: Invite, learner_id: int) -> None:
    """The code's first use: from now on it logs this learner in."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.invite_codes SET learner_id = :learner, used_at = now() "
                "WHERE id = :id AND learner_id IS NULL"
            ),
            {"learner": learner_id, "id": invite.id},
        )
