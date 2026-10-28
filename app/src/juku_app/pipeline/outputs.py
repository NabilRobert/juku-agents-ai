"""What each agent of the weekly pipeline returns, as typed PydanticAI outputs (ADR-007).

Keiko's plan names words by ID, each with the level it claims, and may
propose memory notes (MEM-R2: proposals only; juku_data.memory decides).
Tadashi's review lists issues with a severity, as Pitstop's critic does; a
missing severity counts as high. Code's own checks report issues in the
same shape, marked as code's.
"""

from __future__ import annotations

from typing import Literal

from juku_data.memory import NoteProposal
from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["high", "medium", "low"]
Grade = Literal["A", "B", "C", "D", "F"]


class PipelineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanWord(PipelineModel):
    word_id: str = Field(description="A word ID from the candidates in the facts")
    level: int = Field(description="The word's JLPT level, as the candidates give it (5 is N5)")
    reason: str = Field(description="Why this word this week, in Indonesian")


class KeikoPlan(PipelineModel):
    """Next week's focus, chosen only from the engine's candidates and the mistakes queue."""

    focus: list[PlanWord] = Field(default_factory=list[PlanWord])
    review_word_ids: list[str] = Field(default_factory=list[str], description="Word IDs from the mistakes queue")
    explanation: str = Field(description="Why, in Indonesian, citing facts as [ref:<id>]")
    note_proposals: list[NoteProposal] = Field(default_factory=list[NoteProposal])


class Issue(PipelineModel):
    quote: str = ""
    reason: str
    severity: Severity = "high"
    # "tadashi", or "code" with `kind` naming the check (number_not_in_facts, stale_claim, ...).
    source: str = "tadashi"
    kind: str | None = None


class Review(PipelineModel):
    """Tadashi's verdict on one output, against exactly what its author was given."""

    grade: Grade | None
    issues: list[Issue] = Field(default_factory=list[Issue])
    feedback: str = ""
