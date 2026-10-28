"""get_memory (MEM-R6): the token's learner's notes, with their evidence, and no one else's."""

from datetime import UTC, datetime, timedelta

from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_data.engine.api import record_quiz_answer
from juku_data.engine.models import Learner
from juku_data.memory import NoteProposal, propose_note
from mcp import Client
from mcp_helpers import Learners, call, token_for
from sqlalchemy import text

NOW = datetime.now(UTC)


async def note_for(db: Databases, rules: Rules, learner: Learner, word_offset: int, note: str) -> None:
    async with db.app.connect() as connection:
        word_id = str(
            await connection.scalar(
                text(
                    "SELECT word_id FROM learning.dictionary_words WHERE level = 4 ORDER BY word_id OFFSET :o LIMIT 1"
                ),
                {"o": word_offset},
            )
        )
    ids: list[int] = []
    for days_ago in (3, 2, 1):
        await record_quiz_answer(db, learner.id, word_id, "meaning", False, NOW - timedelta(days=days_ago))
        async with db.app.connect() as connection:
            ids.append(
                int(
                    await connection.scalar(
                        text("SELECT max(id) FROM learning.learning_events WHERE learner_id = :l"), {"l": learner.id}
                    )
                )
            )
    proposal = NoteProposal(category="recurring_confusion", text=note, evidence_event_ids=ids)
    assert (await propose_note(db, learner.id, proposal, proposed_by="keiko", rules=rules, now=NOW)).is_accepted


async def test_get_memory_returns_the_tokens_learners_notes_and_no_one_elses(
    client: Client, signer: Signer, learners: Learners, engine_databases: Databases, rules: Rules
) -> None:

    await note_for(engine_databases, rules, learners.a, 10, "Catatan untuk A.")
    await note_for(engine_databases, rules, learners.b, 11, "Catatan untuk B.")
    answer = await call(client, "get_memory", token_for(signer, learners.a))
    assert not answer.is_error
    assert [note["text"] for note in answer.body["notes"]] == ["Catatan untuk A."]
    [note] = answer.body["notes"]
    assert note["note_id"].startswith("note-")
    assert len(note["evidence"]) == 3
    assert "Catatan untuk B." not in answer.text


async def test_juku_mcp_can_read_the_notes_but_not_the_refused_proposals(engine_databases: Databases) -> None:
    async with engine_databases.app.connect() as connection:
        await connection.execute(text("SET ROLE juku_mcp"))
        await connection.execute(text("SELECT count(*) FROM learning.memory_notes"))
        await connection.rollback()
    async with engine_databases.app.connect() as connection:
        await connection.execute(text("SET ROLE juku_mcp"))
        try:
            await connection.execute(text("SELECT count(*) FROM learning.memory_note_rejections"))
        except Exception as refused:
            assert "permission denied" in str(refused)
        else:
            raise AssertionError("juku_mcp could read the refused proposals")
