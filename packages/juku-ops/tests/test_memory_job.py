"""The nightly memory consolidation (MEM-R4): every learner's notes kept or lapsed, as a recorded job."""

from datetime import UTC, datetime, timedelta

from juku_common.rules import Rules
from juku_data.engine import Databases, create_learner
from juku_data.engine.api import record_quiz_answer
from juku_data.memory import NoteProposal, propose_note
from juku_ops.memory_job import JOB_NAME, consolidate_all
from sqlalchemy import text

NOW = datetime(2026, 11, 8, 3, 10, tzinfo=UTC)


async def test_the_job_lapses_stale_notes_for_every_learner_and_records_its_run(
    engine_databases: Databases, rules: Rules
) -> None:

    learner = await create_learner(engine_databases, nickname="Malam", target_level=5)
    async with engine_databases.app.connect() as connection:
        word_id = str(
            await connection.scalar(
                text("SELECT word_id FROM learning.dictionary_words ORDER BY word_id OFFSET 500 LIMIT 1")
            )
        )
    proposed_at = NOW - timedelta(days=rules.memory.evidence_max_age_days + 5)
    ids: list[int] = []
    for days_before in (3, 2, 1):
        await record_quiz_answer(
            engine_databases, learner.id, word_id, "reading", False, proposed_at - timedelta(days=days_before)
        )
        async with engine_databases.app.connect() as connection:
            ids.append(
                int(
                    await connection.scalar(
                        text("SELECT max(id) FROM learning.learning_events WHERE learner_id = :l"), {"l": learner.id}
                    )
                )
            )
    proposal = NoteProposal(category="recurring_confusion", text="Sering salah membaca.", evidence_event_ids=ids)
    outcome = await propose_note(
        engine_databases, learner.id, proposal, proposed_by="keiko", rules=rules, now=proposed_at
    )
    assert outcome.is_accepted

    decisions = await consolidate_all(engine_databases.app, engine_databases.app, rules, NOW)

    assert [(d.note_id, d.decision) for d in decisions if d.note_id == outcome.note_id] == [(outcome.note_id, "lapsed")]
    async with engine_databases.app.connect() as connection:
        status = await connection.scalar(
            text("SELECT status FROM monitoring.job_runs WHERE job = :job ORDER BY id DESC LIMIT 1"), {"job": JOB_NAME}
        )
    assert status == "succeeded"
