"""Agent notes in the database: proposals checked and stored, the learner's corrections, and consolidation.

The order of checks on a proposal, each ending it with a reason:
1. its category is allowed, not forbidden (MEM-R3);
2. its text is short and about learning (no forbidden markers);
3. the learner hasn't removed a note of this kind in the suppression window (MEM-R5);
4. the learner has room under the cap on active notes;
5. its evidence exists, is this learner's, is enough, shows the pattern and is recent (MEM-R2);
6. no active note of the same kind already rests on the same evidence.
A refused proposal is recorded with its reason and category, never its
text (Phase 1 MEM2). An accepted one is stored with a copy of its evidence,
so reading memory (Juku's MCP server, the page) never reads the events.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from juku_common.rules import Rules
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_data.engine import Databases
from juku_data.engine.reads import word_details
from juku_data.engine.recompute import rebuild_learners
from juku_data.engine.writes import lock_learner
from juku_data.memory import evidence as rules_of
from juku_data.memory.evidence import EvidenceRow
from juku_data.memory.models import (
    ConsolidationDecision,
    EvidenceEvent,
    Memory,
    MemoryNote,
    NoteProposal,
    ProposalOutcome,
)

# A refused proposal keeps only this much of its category, so a "category" that is really a sentence isn't stored.
MAX_STORED_CATEGORY_CHARS = 40
NO_NOTES = "Shiori has no notes about how this learner learns. Nothing else about them is remembered."
SOME_NOTES = "These notes are all Shiori remembers about how this learner learns, each with its evidence."

EVIDENCE_ROWS = """
SELECT e.id, e.learner_id, t.name, e.item_id, w.level, e.result, e.occurred_at
FROM learning.learning_events e
JOIN learning.event_types t ON t.id = e.event_type
LEFT JOIN learning.dictionary_words w ON w.word_id = e.item_id
WHERE e.id = ANY(:ids)
ORDER BY e.occurred_at, e.id
"""
ROWS_SINCE = """
SELECT e.id, e.learner_id, t.name, e.item_id, w.level, e.result, e.occurred_at
FROM learning.learning_events e
JOIN learning.event_types t ON t.id = e.event_type
LEFT JOIN learning.dictionary_words w ON w.word_id = e.item_id
WHERE e.learner_id = :learner AND e.occurred_at > :since AND e.occurred_at <= :now
ORDER BY e.occurred_at, e.id
"""
RECENTLY_REMOVED = """
SELECT EXISTS (
    SELECT 1 FROM learning.memory_notes
    WHERE learner_id = :learner AND category = :category AND status = 'removed' AND status_changed_at > :since
)
"""
ACTIVE_COUNT = "SELECT count(*) FROM learning.memory_notes WHERE learner_id = :learner AND status = 'active'"
SAME_EVIDENCE = """
SELECT EXISTS (
    SELECT 1 FROM learning.memory_notes
    WHERE learner_id = :learner AND category = :category AND status = 'active' AND evidence_event_ids && :ids
)
"""
INSERT_NOTE = """
INSERT INTO learning.memory_notes
    (learner_id, category, text, evidence_event_ids, evidence, proposed_by, created_at, last_evidence_at)
VALUES (:learner, :category, :text, :ids, CAST(:evidence AS jsonb), :by, :now, :last_evidence_at)
RETURNING id
"""
INSERT_REJECTION = """
INSERT INTO learning.memory_note_rejections (learner_id, proposed_by, category, reason, rejected_at)
VALUES (:learner, :by, :category, :reason, :now)
"""
SET_STATUS = """
UPDATE learning.memory_notes SET status = :status, status_reason = :reason, status_changed_at = :now
WHERE id = :id AND learner_id = :learner AND status = 'active'
"""
ACTIVE_NOTES = """
SELECT id, category, text, evidence, created_at, last_evidence_at FROM learning.memory_notes
WHERE learner_id = :learner AND status = 'active' ORDER BY created_at, id
"""
LEARNER_TIMEZONE = "SELECT timezone FROM learning.learners WHERE id = :learner"


class NoteNotFoundError(Exception):
    """No active note with this ID for this learner."""


def _row(record: Any) -> EvidenceRow:
    event_id, learner_id, event_type, item_id, level, result, occurred_at = record
    return EvidenceRow(
        event_id=int(event_id),
        learner_id=int(learner_id),
        event_type=str(event_type),
        item_id=str(item_id),
        level=None if level is None else int(level),
        is_correct=None if result is None else bool(result),
        occurred_at=occurred_at,
    )


async def _snapshot(db: Databases, rows: list[EvidenceRow]) -> list[dict[str, Any]]:
    """The evidence as stored on the note: each row, with its word and reading when it's about a word."""
    words = await word_details(db.dictionary, [row.item_id for row in rows if row.event_type != "sentence_read"])
    snapshot: list[dict[str, Any]] = []
    for row in rows:
        word = words.get(row.item_id)
        snapshot.append(
            {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "word_id": row.item_id if word else None,
                "word": word[0] if word else None,
                "reading": word[1] if word else None,
                "level": row.level,
                "is_correct": row.is_correct,
                "occurred_at": row.occurred_at.isoformat(),
            }
        )
    return snapshot


async def _refuse(  # noqa: PLR0913 (the refusal row's fields, inside the caller's transaction)
    connection: AsyncConnection, learner_id: int, proposal: NoteProposal, proposed_by: str, reason: str, now: datetime
) -> ProposalOutcome:
    await connection.execute(
        text(INSERT_REJECTION),
        {
            "learner": learner_id,
            "by": proposed_by,
            "category": proposal.category[:MAX_STORED_CATEGORY_CHARS],
            "reason": reason,
            "now": now,
        },
    )
    return ProposalOutcome(is_accepted=False, reason=reason)


async def _reason_before_evidence(
    connection: AsyncConnection, learner_id: int, proposal: NoteProposal, rules: Rules, now: datetime
) -> str | None:
    """Checks 1-4: the category, the text, the suppression window and the cap."""
    memory = rules.memory
    reason = rules_of.check_category(proposal.category, memory) or rules_of.check_text(proposal.text, memory)
    if reason:
        return reason
    since = now - timedelta(days=memory.suppress_after_removal_days)
    if await connection.scalar(
        text(RECENTLY_REMOVED), {"learner": learner_id, "category": proposal.category, "since": since}
    ):
        return rules_of.SUPPRESSED
    if int(await connection.scalar(text(ACTIVE_COUNT), {"learner": learner_id}) or 0) >= memory.max_active_notes:
        return rules_of.NOTE_CAP_REACHED
    return None


async def propose_note(  # noqa: PLR0913 (memory's public API; the rest are keyword-only)
    db: Databases, learner_id: int, proposal: NoteProposal, *, proposed_by: str, rules: Rules, now: datetime
) -> ProposalOutcome:
    """Store the note if it passes every check; otherwise record why not. One transaction, the learner locked."""
    async with db.app.begin() as connection:
        await lock_learner(connection, learner_id)
        reason = await _reason_before_evidence(connection, learner_id, proposal, rules, now)
        if reason:
            return await _refuse(connection, learner_id, proposal, proposed_by, reason, now)
        ids = sorted(set(proposal.evidence_event_ids))
        rows = [_row(record) for record in (await connection.execute(text(EVIDENCE_ROWS), {"ids": ids})).all()]
        reason = rules_of.check_evidence(proposal.category, ids, rows, learner_id, rules.memory, now)
        if reason is None and await connection.scalar(
            text(SAME_EVIDENCE), {"learner": learner_id, "category": proposal.category, "ids": ids}
        ):
            reason = rules_of.DUPLICATE
        if reason:
            return await _refuse(connection, learner_id, proposal, proposed_by, reason, now)
        note_id = await connection.scalar(
            text(INSERT_NOTE),
            {
                "learner": learner_id,
                "category": proposal.category,
                "text": proposal.text.strip(),
                "ids": ids,
                "evidence": json.dumps(await _snapshot(db, rows), ensure_ascii=False),
                "by": proposed_by,
                "now": now,
                "last_evidence_at": max(row.occurred_at for row in rows),
            },
        )
    return ProposalOutcome(is_accepted=True, note_id=int(note_id))


async def _set_status(db: Databases, learner_id: int, note_id: int, status: str, reason: str, now: datetime) -> None:  # noqa: PLR0913 (one status change's fields)
    async with db.app.begin() as connection:
        changed = await connection.execute(
            text(SET_STATUS), {"status": status, "reason": reason, "now": now, "id": note_id, "learner": learner_id}
        )
    if changed.rowcount == 0:
        raise NoteNotFoundError(f"no active note {note_id} for this learner")


async def remove_note(db: Databases, learner_id: int, note_id: int, now: datetime) -> None:
    """The learner removes a note (MEM-R5); the same kind of note is held back for the suppression window."""
    await _set_status(db, learner_id, note_id, "removed", "removed_by_learner", now)


async def mark_note_wrong(db: Databases, learner_id: int, note_id: int, now: datetime) -> None:
    """The learner says a note is wrong (MEM-R5); it's no longer used, and it counts towards MEM3."""
    await _set_status(db, learner_id, note_id, "wrong", "marked_wrong_by_learner", now)


def _evidence_event(item: dict[str, Any], zone: ZoneInfo) -> EvidenceEvent:
    return EvidenceEvent(
        event_id=int(item["event_id"]),
        event_type=str(item["event_type"]),
        word_id=item["word_id"],
        word=item["word"],
        reading=item["reading"],
        level=item["level"],
        is_correct=item["is_correct"],
        occurred_on=datetime.fromisoformat(str(item["occurred_at"])).astimezone(zone).date(),
    )


async def get_memory(db: Databases, learner_id: int, now: datetime) -> Memory:
    """The learner's active notes, with their evidence and age: what get_memory and the page show (MEM-R6)."""
    async with db.app.connect() as connection:
        zone = ZoneInfo(str(await connection.scalar(text(LEARNER_TIMEZONE), {"learner": learner_id}) or "UTC"))
        records = (await connection.execute(text(ACTIVE_NOTES), {"learner": learner_id})).all()
    notes = [
        MemoryNote(
            note_id=f"note-{note_id}",
            category=str(category),
            text=str(note_text),
            evidence=[_evidence_event(item, zone) for item in cast(list[dict[str, Any]], evidence)],
            noted_on=created_at.astimezone(zone).date(),
            last_evidence_on=last_evidence_at.astimezone(zone).date(),
            age_days=max(0, (now - created_at).days),
        )
        for note_id, category, note_text, evidence, created_at, last_evidence_at in records
    ]
    return Memory(notes=notes, note=SOME_NOTES if notes else NO_NOTES)


def _stored_rows(learner_id: int, evidence: list[dict[str, Any]]) -> list[EvidenceRow]:
    return [
        EvidenceRow(
            event_id=int(item["event_id"]),
            learner_id=learner_id,
            event_type=str(item["event_type"]),
            item_id=str(item["word_id"] or ""),
            level=item["level"],
            is_correct=item["is_correct"],
            occurred_at=datetime.fromisoformat(str(item["occurred_at"])),
        )
        for item in evidence
    ]


async def consolidate(app: AsyncEngine, learner_id: int, rules: Rules, now: datetime) -> list[ConsolidationDecision]:
    """MEM-R4: recompute what's known, then keep or lapse each active note, recording why. One transaction."""
    decisions: list[ConsolidationDecision] = []
    async with app.begin() as connection:
        await lock_learner(connection, learner_id)
        await rebuild_learners(connection, [learner_id])
        records = (
            await connection.execute(
                text(
                    "SELECT id, category, evidence, last_evidence_at FROM learning.memory_notes "
                    "WHERE learner_id = :learner AND status = 'active' ORDER BY id"
                ),
                {"learner": learner_id},
            )
        ).all()
        for note_id, category, evidence, last_evidence_at in records:
            stored = _stored_rows(learner_id, cast(list[dict[str, Any]], evidence))
            newer_records = await connection.execute(
                text(ROWS_SINCE), {"learner": learner_id, "since": min(row.occurred_at for row in stored), "now": now}
            )
            newer = [
                row for row in map(_row, newer_records.all()) if row.event_id not in {item.event_id for item in stored}
            ]
            decision, reason = rules_of.consolidation_decision(str(category), stored, newer, rules.memory, now)
            supported = [row.occurred_at for row in newer if rules_of.recurs(str(category), stored, row)]
            if decision == "lapsed":
                await connection.execute(
                    text(SET_STATUS),
                    {"status": "lapsed", "reason": reason, "now": now, "id": note_id, "learner": learner_id},
                )
            elif supported:
                await connection.execute(
                    text("UPDATE learning.memory_notes SET last_evidence_at = :at WHERE id = :id"),
                    {"at": max([last_evidence_at, *supported]), "id": note_id},
                )
            await connection.execute(
                text(
                    "INSERT INTO learning.memory_consolidations (learner_id, note_id, decided_at, decision, reason) "
                    "VALUES (:learner, :note, :now, :decision, :reason)"
                ),
                {"learner": learner_id, "note": note_id, "now": now, "decision": decision, "reason": reason},
            )
            decisions.append(ConsolidationDecision(note_id=int(note_id), decision=decision, reason=reason, at=now))
    return decisions
