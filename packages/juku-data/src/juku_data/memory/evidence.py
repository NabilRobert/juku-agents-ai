"""The rules a proposed note must pass, and the weekly decision to keep or lapse it (MEM-R2 to MEM-R4).

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
from datetime import datetime, timedelta

from juku_common.rules import MemoryRules

from juku_data.memory.models import Decision

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
    if category in rules.forbidden_categories:
        return FORBIDDEN_CATEGORY
    if category not in rules.allowed_categories:
        return UNKNOWN_CATEGORY
    return None


def check_text(note_text: str, rules: MemoryRules) -> str | None:
    stripped = note_text.strip()
    if not stripped:
        return EMPTY_TEXT
    if len(stripped) > rules.max_text_chars:
        return TEXT_TOO_LONG
    lowered = stripped.lower()
    if any(marker in lowered for marker in rules.forbidden_text_markers):
        return FORBIDDEN_CONTENT
    return None


def shows_pattern(category: str, rows: Sequence[EvidenceRow]) -> bool:
    """Whether every row together shows the category's pattern (see the module docstring)."""
    if category == "recurring_confusion":
        kinds = {row.event_type for row in rows}
        return len(kinds) == 1 and kinds <= QUIZ_TYPES and all(row.is_correct is False for row in rows)
    if category == "preferred_example":
        return all(row.event_type == "sentence_read" for row in rows)
    if category == "pace":
        days = {row.occurred_at.date() for row in rows}
        return all(row.event_type == "marked_known" for row in rows) and len(days) >= PACE_MIN_DAYS
    if category == "avoided_level":
        levels = {row.level for row in rows}
        return len(levels) == 1 and None not in levels and all(_is_avoidance(row) for row in rows)
    return False


def _is_avoidance(row: EvidenceRow) -> bool:
    return row.event_type == "unmarked_known" or (row.event_type in QUIZ_TYPES and row.is_correct is False)


def check_evidence(
    category: str,
    requested_ids: Sequence[int],
    rows: Sequence[EvidenceRow],
    learner_id: int,
    rules: MemoryRules,
    now: datetime,
) -> str | None:
    """None if the rows behind a proposal exist, are this learner's, are enough, show the pattern, and are recent."""
    found = {row.event_id for row in rows}
    if not requested_ids or any(event_id not in found for event_id in requested_ids):
        return EVIDENCE_NOT_FOUND
    if any(row.learner_id != learner_id for row in rows):
        return EVIDENCE_NOT_THIS_LEARNERS
    if len(found) < rules.min_evidence_events:
        return TOO_LITTLE_EVIDENCE
    if not shows_pattern(category, rows):
        return NO_PATTERN
    newest = max(row.occurred_at for row in rows)
    if now - newest > timedelta(days=rules.evidence_max_age_days):
        return EVIDENCE_TOO_OLD
    return None


def recurs(category: str, evidence: Sequence[EvidenceRow], row: EvidenceRow) -> bool:
    """Whether a newer row shows the note's pattern again."""
    if category == "recurring_confusion":
        kinds = {item.event_type for item in evidence}
        words = {item.item_id for item in evidence}
        return row.event_type in kinds and row.item_id in words and row.is_correct is False
    if category == "preferred_example":
        return row.event_type == "sentence_read"
    if category == "pace":
        return row.event_type == "marked_known"
    if category == "avoided_level":
        return row.level in {item.level for item in evidence} and _is_avoidance(row)
    return False


def contradicts(category: str, evidence: Sequence[EvidenceRow], row: EvidenceRow) -> bool:
    """Whether a newer row goes against the note: for a confusion, a right answer of the same kind on its words."""
    if category != "recurring_confusion":
        return False
    kinds = {item.event_type for item in evidence}
    words = {item.item_id for item in evidence}
    return row.event_type in kinds and row.item_id in words and row.is_correct is True


def consolidation_decision(
    category: str, evidence: Sequence[EvidenceRow], newer: Sequence[EvidenceRow], rules: MemoryRules, now: datetime
) -> tuple[Decision, str]:
    """("kept" or "lapsed", the reason), from the note's evidence and the learner's activity since it."""
    support_since = [row for row in newer if recurs(category, evidence, row)]
    last_support = max(row.occurred_at for row in [*evidence, *support_since])
    against = [row for row in newer if row.occurred_at > last_support and contradicts(category, evidence, row)]
    if len(against) >= rules.contradicting_answers:
        return "lapsed", CONTRADICTED
    if now - last_support > timedelta(days=rules.evidence_max_age_days):
        return "lapsed", EVIDENCE_TOO_OLD
    return "kept", RECURRED if support_since else EVIDENCE_RECENT
