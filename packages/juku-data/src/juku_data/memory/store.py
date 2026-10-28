"""Stubs until the memory slice's code lands (EDD1): the tests are written against these signatures."""

from __future__ import annotations

from datetime import datetime

from juku_common.rules import Rules

from juku_data.engine import Databases
from juku_data.memory.models import ConsolidationDecision, Memory, NoteProposal, ProposalOutcome


class NoteNotFoundError(Exception):
    """No such note for this learner."""


async def propose_note(
    db: Databases, learner_id: int, proposal: NoteProposal, *, proposed_by: str, rules: Rules, now: datetime
) -> ProposalOutcome:
    raise NotImplementedError


async def remove_note(db: Databases, learner_id: int, note_id: int, now: datetime) -> None:
    raise NotImplementedError


async def mark_note_wrong(db: Databases, learner_id: int, note_id: int, now: datetime) -> None:
    raise NotImplementedError


async def get_memory(db: Databases, learner_id: int, now: datetime) -> Memory:
    raise NotImplementedError


async def consolidate(db: Databases, learner_id: int, rules: Rules, now: datetime) -> list[ConsolidationDecision]:
    raise NotImplementedError
