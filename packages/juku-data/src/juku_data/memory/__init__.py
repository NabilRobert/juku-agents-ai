"""Agent notes about how a learner learns: proposed by agents, accepted only with evidence (ADR-008).

The engine (juku_data.engine) already holds the other two kinds of memory,
what the learner knows and what happened. This package holds the third.
"""

from juku_data.memory.models import (
    ConsolidationDecision,
    EvidenceEvent,
    Memory,
    MemoryNote,
    NoteProposal,
    ProposalOutcome,
)
from juku_data.memory.store import (
    NoteNotFoundError,
    consolidate,
    get_memory,
    mark_note_wrong,
    propose_note,
    remove_note,
)

__all__ = [
    "ConsolidationDecision",
    "EvidenceEvent",
    "Memory",
    "MemoryNote",
    "NoteNotFoundError",
    "NoteProposal",
    "ProposalOutcome",
    "consolidate",
    "get_memory",
    "mark_note_wrong",
    "propose_note",
    "remove_note",
]
