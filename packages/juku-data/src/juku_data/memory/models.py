"""Memory's typed shapes (ADR-008; Phase 2 MEM-R1 to MEM-R5).

`NoteProposal` is what an agent returns in its structured output (a
PydanticAI output type): a category, a short text and the IDs of the
activity rows behind it. It is only a proposal: code decides whether it
becomes a note (juku_data.memory.store). The category is a plain string on
purpose, so a forbidden one reaches the code, is refused there and is
counted (MEM2), rather than being bounced by validation unseen.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NoteStatus = Literal["active", "lapsed", "removed", "wrong"]
Decision = Literal["kept", "lapsed"]


class NoteProposal(BaseModel):
    """One note an agent proposes. Code stores it only if its evidence shows the pattern."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="One of the allowed learning categories, e.g. recurring_confusion")
    text: str = Field(description="One short sentence in Indonesian about how the learner learns")
    evidence_event_ids: list[int] = Field(description="IDs of the learner's activity rows that show the pattern")


class MemoryModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProposalOutcome(MemoryModel):
    """Accepted with the new note's ID, or rejected with a reason category (MEM2)."""

    is_accepted: bool
    note_id: int | None = None
    reason: str | None = None


class EvidenceEvent(MemoryModel):
    """One activity row behind a note, copied when the note is accepted, so reading memory never reads events."""

    event_id: int
    event_type: str
    word_id: str | None
    word: str | None
    reading: str | None
    level: int | None
    is_correct: bool | None
    occurred_on: date


class MemoryNote(MemoryModel):
    note_id: str
    category: str
    text: str
    evidence: list[EvidenceEvent]
    noted_on: date
    last_evidence_on: date
    age_days: int


class Memory(MemoryModel):
    """What get_memory returns: the learner's active notes, with their evidence and age."""

    notes: list[MemoryNote]
    note: str


class ConsolidationDecision(MemoryModel):
    note_id: int
    decision: Decision
    reason: str
    at: datetime
