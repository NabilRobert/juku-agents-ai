"""Stubs until the memory slice's code lands (EDD1).

The rules a proposed note must pass, and the weekly decision to keep or lapse it (MEM-R2 to MEM-R4).

Pure functions over the evidence rows, so they're tested directly and
mutation-tested; juku_data.memory.store fetches the rows and applies them.

What each allowed category's evidence must show (at least
`min_evidence_events` rows, all of them):
- recurring_confusion: wrong answers to the same kind of quiz (meaning, or reading);
- preferred_example: sentences read;
- pace: words marked known, on at least two different days;
- avoided_level: wrong answers or unmarked words, all at one JLPT level.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from juku_common.rules import MemoryRules

QUIZ_TYPES = frozenset({"quiz_meaning", "quiz_reading"})
# Reasons a proposal is refused (Phase 1 MEM2: every rejection categorised).
UNKNOWN_CATEGORY = "unknown_category"
FORBIDDEN_CATEGORY = "forbidden_category"
EMPTY_TEXT = "empty_text"
TEXT_TOO_LONG = "text_too_long"
FORBIDDEN_CONTENT = "forbidden_content"
EVIDENCE_NOT_FOUND = "evidence_not_found"
EVIDENCE_NOT_THIS_LEARNERS = "evidence_not_this_learners"
TOO_LITTLE_EVIDENCE = "too_little_evidence"
NO_PATTERN = "evidence_does_not_show_pattern"
EVIDENCE_TOO_OLD = "evidence_too_old"
SUPPRESSED = "suppressed_after_removal"
NOTE_CAP_REACHED = "note_cap_reached"
DUPLICATE = "duplicate"
# Reasons the weekly consolidation gives (MEM-R4: why each note was kept or dropped).
CONTRADICTED = "contradicted_by_newer_activity"
RECURRED = "recurred"
EVIDENCE_RECENT = "evidence_recent"
PACE_MIN_DAYS = 2


@dataclass(frozen=True)
class EvidenceRow:
    """One activity row, as the rules see it."""

    event_id: int
    learner_id: int
    event_type: str
    item_id: str
    level: int | None
    is_correct: bool | None
    occurred_at: datetime


def check_category(category: str, rules: MemoryRules) -> str | None:
    raise NotImplementedError


def check_text(note_text: str, rules: MemoryRules) -> str | None:
    raise NotImplementedError


def shows_pattern(category: str, rows: Sequence[EvidenceRow]) -> bool:
    raise NotImplementedError


def check_evidence(
    category: str,
    requested_ids: Sequence[int],
    rows: Sequence[EvidenceRow],
    learner_id: int,
    rules: MemoryRules,
    now: datetime,
) -> str | None:
    raise NotImplementedError


def recurs(category: str, evidence: Sequence[EvidenceRow], row: EvidenceRow) -> bool:
    raise NotImplementedError


def contradicts(category: str, evidence: Sequence[EvidenceRow], row: EvidenceRow) -> bool:
    raise NotImplementedError


def consolidation_decision(
    category: str, evidence: Sequence[EvidenceRow], newer: Sequence[EvidenceRow], rules: MemoryRules, now: datetime
) -> tuple[str, str]:
    raise NotImplementedError
