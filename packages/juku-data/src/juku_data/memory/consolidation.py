"""Memory consolidation (MEM-R4): the nightly review that keeps or lapses each active note.

What the learner knows is recomputed first, then each note is judged against
the events since its evidence, and the decision and its reason are recorded.
It all runs in one transaction, so a note is never left half-reviewed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from juku_common.rules import Rules
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_data.engine.recompute import rebuild_learners
from juku_data.engine.writes import lock_learner
from juku_data.memory import evidence as rules_of
from juku_data.memory.evidence import EvidenceRow
from juku_data.memory.models import ConsolidationDecision
from juku_data.memory.store import SET_STATUS, evidence_row

ROWS_SINCE = """
SELECT e.id, e.learner_id, t.name, e.item_id, w.level, e.result, e.occurred_at
FROM learning.learning_events e
JOIN learning.event_types t ON t.id = e.event_type
LEFT JOIN learning.dictionary_words w ON w.word_id = e.item_id
WHERE e.learner_id = :learner AND e.occurred_at > :since AND e.occurred_at <= :now
ORDER BY e.occurred_at, e.id
"""
ACTIVE_NOTE_EVIDENCE = """
SELECT id, category, evidence, last_evidence_at FROM learning.memory_notes
WHERE learner_id = :learner AND status = 'active' ORDER BY id
"""
RECORD_DECISION = """
INSERT INTO learning.memory_consolidations (learner_id, note_id, decided_at, decision, reason)
VALUES (:learner, :note, :now, :decision, :reason)
"""


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


async def _rows_after_evidence(
    connection: AsyncConnection, learner_id: int, stored: list[EvidenceRow], now: datetime
) -> list[EvidenceRow]:
    """The learner's events since the note's earliest evidence, leaving out the evidence itself."""
    since = min(row.occurred_at for row in stored)
    records = await connection.execute(text(ROWS_SINCE), {"learner": learner_id, "since": since, "now": now})
    evidence_ids = {row.event_id for row in stored}
    return [row for row in map(evidence_row, records.all()) if row.event_id not in evidence_ids]


async def _review_note(
    connection: AsyncConnection, learner_id: int, note: Any, rules: Rules, now: datetime
) -> ConsolidationDecision:
    note_id, category, evidence, last_evidence_at = note
    stored = _stored_rows(learner_id, cast(list[dict[str, Any]], evidence))
    newer = await _rows_after_evidence(connection, learner_id, stored, now)
    decision, reason = rules_of.consolidation_decision(str(category), stored, newer, rules.memory, now)
    supported = [row.occurred_at for row in newer if rules_of.recurs(str(category), stored, row)]
    if decision == "lapsed":
        await connection.execute(
            text(SET_STATUS), {"status": "lapsed", "reason": reason, "now": now, "id": note_id, "learner": learner_id}
        )
    elif supported:
        await connection.execute(
            text("UPDATE learning.memory_notes SET last_evidence_at = :at WHERE id = :id"),
            {"at": max([last_evidence_at, *supported]), "id": note_id},
        )
    await connection.execute(
        text(RECORD_DECISION),
        {"learner": learner_id, "note": note_id, "now": now, "decision": decision, "reason": reason},
    )
    return ConsolidationDecision(note_id=int(note_id), decision=decision, reason=reason, at=now)


async def consolidate(app: AsyncEngine, learner_id: int, rules: Rules, now: datetime) -> list[ConsolidationDecision]:
    """MEM-R4: recompute what's known, then keep or lapse each active note, recording why. One transaction."""
    decisions: list[ConsolidationDecision] = []
    async with app.begin() as connection:
        await lock_learner(connection, learner_id)
        await rebuild_learners(connection, [learner_id])
        notes = (await connection.execute(text(ACTIVE_NOTE_EVIDENCE), {"learner": learner_id})).all()
        for note in notes:
            decisions.append(await _review_note(connection, learner_id, note, rules, now))
    return decisions
