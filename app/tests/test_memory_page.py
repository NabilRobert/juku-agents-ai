"""The "Shiori ingat…" page (MEM-R5): every note with its evidence, and the learner's own corrections."""

import json
from datetime import UTC, datetime, timedelta

from juku_app.invites import issue_codes
from juku_common.rules import load_rules
from juku_data.engine import Databases, mark_known
from juku_data.engine.api import record_quiz_answer
from juku_data.memory import NoteProposal, propose_note
from sqlalchemy import text
from web_helpers import client_for, csrf_header, deps, found, sign_up


async def learner_id_of(db: Databases, nickname: str) -> int:
    async with db.app.connect() as connection:
        return int(
            await connection.scalar(text("SELECT id FROM learning.learners WHERE nickname = :n"), {"n": nickname})
        )


async def a_word(db: Databases, offset: int) -> str:
    async with db.app.connect() as connection:
        return str(
            await connection.scalar(
                text(
                    "SELECT word_id FROM learning.dictionary_words WHERE level = 5 ORDER BY word_id OFFSET :o LIMIT 1"
                ),
                {"o": offset},
            )
        )


async def a_note(db: Databases, learner_id: int, word_id: str) -> int:
    """Three wrong reading answers on one word, and the note they support."""
    now = datetime.now(UTC)
    ids: list[int] = []
    for days_ago in (3, 2, 1):
        await record_quiz_answer(db, learner_id, word_id, "reading", False, now - timedelta(days=days_ago))
        async with db.app.connect() as connection:
            ids.append(
                int(
                    await connection.scalar(
                        text("SELECT max(id) FROM learning.learning_events WHERE learner_id = :l"), {"l": learner_id}
                    )
                )
            )
    proposal = NoteProposal(
        category="recurring_confusion", text="Sering salah membaca kata ini.", evidence_event_ids=ids
    )
    outcome = await propose_note(db, learner_id, proposal, proposed_by="keiko", rules=load_rules(), now=now)
    assert outcome.note_id is not None
    return outcome.note_id


async def note_status(db: Databases, note_id: int) -> str:
    async with db.app.connect() as connection:
        return str(
            await connection.scalar(text("SELECT status FROM learning.memory_notes WHERE id = :id"), {"id": note_id})
        )


async def test_the_page_shows_each_note_with_its_evidence_and_the_known_words(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Rina")
        learner_id = await learner_id_of(engine_databases, "Rina")
        await a_note(engine_databases, learner_id, await a_word(engine_databases, 300))
        await mark_known(engine_databases, learner_id, await a_word(engine_databases, 301), datetime.now(UTC))
        page = await client.get("/ingat")
    assert page.status_code == 200
    data = json.loads(found(r'<script type="application/json" id="memory-data">(.*?)</script>', page.text))
    [note] = data["notes"]
    assert note["text"] == "Sering salah membaca kata ini."
    assert len(note["evidence"]) == 3
    assert len(data["words"]) == 1
    assert "Shiori ingat" in page.text


async def test_a_learner_removes_a_note_and_marks_another_wrong(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Sari")
        learner_id = await learner_id_of(engine_databases, "Sari")
        removed = await a_note(engine_databases, learner_id, await a_word(engine_databases, 310))
        wrong = await a_note(engine_databases, learner_id, await a_word(engine_databases, 311))
        page = await client.get("/ingat")
        assert (await client.post(f"/ingat/catatan/note-{removed}/hapus", headers=csrf_header(page))).status_code == 204
        assert (await client.post(f"/ingat/catatan/note-{wrong}/salah", headers=csrf_header(page))).status_code == 204
    assert (await note_status(engine_databases, removed), await note_status(engine_databases, wrong)) == (
        "removed",
        "wrong",
    )


async def test_a_learner_unmarks_a_known_word(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Tari")
        learner_id = await learner_id_of(engine_databases, "Tari")
        word_id = await a_word(engine_databases, 320)
        await mark_known(engine_databases, learner_id, word_id, datetime.now(UTC))
        page = await client.get("/ingat")
        response = await client.post(f"/ingat/kata/{word_id}/belum", headers=csrf_header(page))
    assert response.status_code == 204
    async with engine_databases.app.connect() as connection:
        is_known = await connection.scalar(
            text("SELECT is_known FROM learning.learner_state WHERE learner_id = :l AND item_id = :w"),
            {"l": learner_id, "w": word_id},
        )
    assert is_known is False


async def test_a_learner_cant_touch_another_learners_note(engine_databases: Databases) -> None:
    owner_code, other_code = await issue_codes(engine_databases.app, 2)
    async with client_for(deps(engine_databases)) as owner:
        await sign_up(owner, owner_code, nickname="Umi")
    note_id = await a_note(
        engine_databases, await learner_id_of(engine_databases, "Umi"), await a_word(engine_databases, 330)
    )
    async with client_for(deps(engine_databases)) as other:
        await sign_up(other, other_code, nickname="Vina")
        page = await other.get("/ingat")
        response = await other.post(f"/ingat/catatan/note-{note_id}/hapus", headers=csrf_header(page))
    assert response.status_code == 404
    assert await note_status(engine_databases, note_id) == "active"


async def test_a_correction_without_the_csrf_token_is_refused(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Wati")
        note_id = await a_note(
            engine_databases, await learner_id_of(engine_databases, "Wati"), await a_word(engine_databases, 340)
        )
        response = await client.post(f"/ingat/catatan/note-{note_id}/hapus")
    assert response.status_code == 403
    assert await note_status(engine_databases, note_id) == "active"
