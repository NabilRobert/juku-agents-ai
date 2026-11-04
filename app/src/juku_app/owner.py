"""The owner's actions (ADR-029): issue invite codes, remove a learner, change a role, each one audited.

Arthur is the owner and also an ordinary learner. These functions are the
only way into the three actions, from the owner page (routes/owner.py) or
the server's command line (`juku invite`, `juku delete-learner`,
`juku set-role`). Each action and its row in `app.owner_actions` commit
together, so there's no action without its audit row.

Only `set_role`, which has no page, can make someone owner: a learner
can't reach it from the web app at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from juku_data.engine import LearnerNotFoundError
from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_app import invites, privacy

Role = Literal["owner", "learner"]
Place = Literal["page", "cli"]
Action = Literal["issue_codes", "remove_learner", "set_role"]
# The same limit as `juku invite --count`: enough for a class, small enough to hand out by hand.
MAX_CODES_AT_ONCE = 100
# Enough to see the recent history, small enough to load at once.
RECENT_ACTIONS = 50

FIND_LEARNER = "SELECT id, role FROM learning.learners WHERE public_id = :public_id FOR UPDATE"
LEARNERS = """
SELECT public_id, nickname, role, target_level, created_at, last_active_at
FROM learning.learners ORDER BY created_at
"""
ACTIONS = """
SELECT a.acted_at, a.place, a.action, a.subject, a.detail, o.public_id AS owner
FROM app.owner_actions a LEFT JOIN learning.learners o ON o.id = a.owner_id
ORDER BY a.id DESC LIMIT :limit
"""
RECORD = """
INSERT INTO app.owner_actions (owner_id, place, action, subject, detail)
VALUES (:owner, :place, :action, :subject, CAST(:detail AS jsonb))
"""


class OwnerActionRefusedError(Exception):
    """The action isn't allowed: the message says why and what to do instead."""


@dataclass(frozen=True)
class Actor:
    """Who acts, and from where. The command line has no signed-in learner, so no owner ID."""

    place: Place
    owner_id: int | None = None


COMMAND_LINE = Actor(place="cli")


async def is_owner(engine: AsyncEngine, learner_id: int) -> bool:
    async with engine.connect() as connection:
        role = await connection.scalar(text("SELECT role FROM learning.learners WHERE id = :id"), {"id": learner_id})
    return role == "owner"


async def _record(
    connection: AsyncConnection, actor: Actor, action: Action, subject: str | None, detail: dict[str, Any]
) -> None:
    await connection.execute(
        text(RECORD),
        {
            "owner": actor.owner_id,
            "place": actor.place,
            "action": action,
            "subject": subject,
            "detail": json.dumps(detail),
        },
    )


async def _locked_learner(connection: AsyncConnection, public_id: str) -> RowMapping:
    row = (await connection.execute(text(FIND_LEARNER), {"public_id": public_id})).mappings().first()
    if row is None:
        raise LearnerNotFoundError(f"no learner with public ID {public_id!r}: check it on the owner page")
    return row


async def issue_codes(engine: AsyncEngine, actor: Actor, count: int) -> list[str]:
    """New invite codes, shown once. The audit keeps each code's lookup part, never its secret."""
    if not 1 <= count <= MAX_CODES_AT_ONCE:
        raise OwnerActionRefusedError(f"{count} codes is outside 1 to {MAX_CODES_AT_ONCE}: ask for fewer")
    async with engine.begin() as connection:
        codes = await invites.insert_codes(connection, count)
        lookups = [code.partition(".")[0] for code in codes]
        await _record(connection, actor, "issue_codes", None, {"count": count, "lookups": lookups})
    return codes


async def remove_learner(engine: AsyncEngine, actor: Actor, public_id: str) -> dict[str, int]:
    """Delete everything about one learner (as "Hapus data saya" does). An owner must be made a learner first."""
    async with engine.begin() as connection:
        learner = await _locked_learner(connection, public_id)
        if learner["role"] == "owner":
            raise OwnerActionRefusedError(
                f"{public_id} is an owner: run `juku set-role {public_id} learner` first, "
                "or use Hapus data saya for your own account"
            )
        removed = await privacy.delete_learner_rows(connection, int(learner["id"]))
        await _record(connection, actor, "remove_learner", public_id, {"rows": removed})
    return removed


async def set_role(engine: AsyncEngine, actor: Actor, public_id: str, role: Role) -> None:
    """Make a learner the owner, or an ordinary learner again."""
    async with engine.begin() as connection:
        learner = await _locked_learner(connection, public_id)
        await connection.execute(
            text("UPDATE learning.learners SET role = :role WHERE id = :id"), {"role": role, "id": learner["id"]}
        )
        await _record(connection, actor, "set_role", public_id, {"from": learner["role"], "to": role})


async def learners_and_actions(engine: AsyncEngine) -> tuple[list[RowMapping], list[RowMapping]]:
    """What the owner page shows: every learner, and the latest owner actions."""
    async with engine.connect() as connection:
        learners = (await connection.execute(text(LEARNERS))).mappings().all()
        actions = (await connection.execute(text(ACTIONS), {"limit": RECENT_ACTIONS})).mappings().all()
    return list(learners), list(actions)
