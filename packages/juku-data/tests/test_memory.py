"""Agent notes in the database (ADR-008; MEM-R1 to MEM-R5): proposed, checked, corrected, consolidated."""

from datetime import UTC, datetime, timedelta

import pytest
from juku_common.rules import Rules
from juku_data.engine import Databases, create_learner, mark_known
from juku_data.engine.api import record_quiz_answer
from juku_data.engine.models import Learner
from juku_data.memory import (
    NoteNotFoundError,
    NoteProposal,
    consolidate,
    get_memory,
    mark_note_wrong,
    propose_note,
    remove_note,
)
from sqlalchemy import text

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: memory lands in the next commit")


NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


async def level_words(db: Databases, count: int, offset: int = 0) -> list[str]:
    async with db.app.connect() as connection:
        found = await connection.scalars(
            text("SELECT word_id FROM learning.dictionary_words WHERE level = 5 ORDER BY word_id OFFSET :o LIMIT :n"),
            {"o": offset, "n": count},
        )
        return [str(word_id) for word_id in found]


async def latest_event(db: Databases, learner: Learner) -> int:
    async with db.app.connect() as connection:
        return int(
            await connection.scalar(
                text("SELECT max(id) FROM learning.learning_events WHERE learner_id = :l"), {"l": learner.id}
            )
        )


async def three_misses(db: Databases, learner: Learner, word_id: str, *, days_ago: int = 3) -> list[int]:
    """Three wrong reading answers on one word, a day apart, ending `days_ago - 2` days before NOW."""
    ids: list[int] = []
    for offset in range(3):
        at = NOW - timedelta(days=days_ago - offset)
        await record_quiz_answer(db, learner.id, word_id, "reading", False, at)
        ids.append(await latest_event(db, learner))
    return ids


def confusion(evidence: list[int], note: str = "Sering salah membaca kata ini.") -> NoteProposal:
    return NoteProposal(category="recurring_confusion", text=note, evidence_event_ids=evidence)


@pytest.fixture
async def learner(engine_databases: Databases) -> Learner:
    return await create_learner(engine_databases, nickname="Memori", target_level=5)


@pytest.fixture
async def word(engine_databases: Databases) -> str:
    return (await level_words(engine_databases, 1, 40))[0]


async def test_a_note_with_good_evidence_is_stored_with_a_copy_of_its_evidence(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    evidence = await three_misses(engine_databases, learner, word)
    outcome = await propose_note(
        engine_databases, learner.id, confusion(evidence), proposed_by="keiko", rules=rules, now=NOW
    )
    assert outcome.is_accepted and outcome.note_id is not None
    memory = await get_memory(engine_databases, learner.id, NOW)
    [note] = memory.notes
    assert note.note_id == f"note-{outcome.note_id}"
    assert [item.event_id for item in note.evidence] == evidence
    assert {item.word_id for item in note.evidence} == {word}
    assert all(item.word for item in note.evidence), "the evidence carries the word, so reading it needs no join"
    assert note.age_days == 0


async def test_a_refused_proposal_is_counted_by_reason_and_its_text_is_not_kept(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    evidence = await three_misses(engine_databases, learner, word)
    proposal = NoteProposal(category="health", text="Sering lelah setelah lembur.", evidence_event_ids=evidence)
    outcome = await propose_note(engine_databases, learner.id, proposal, proposed_by="keiko", rules=rules, now=NOW)
    assert (outcome.is_accepted, outcome.reason) == (False, "forbidden_category")
    async with engine_databases.app.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT * FROM learning.memory_note_rejections WHERE learner_id = :l"), {"l": learner.id}
            )
        ).mappings()
        stored = [dict(row) for row in rows]
    assert [(row["reason"], row["proposed_by"]) for row in stored] == [("forbidden_category", "keiko")]
    assert "lelah" not in str(stored)


async def test_another_learners_activity_is_not_evidence(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    other = await create_learner(engine_databases, nickname="Lain", target_level=5)
    theirs = await three_misses(engine_databases, other, word)
    outcome = await propose_note(
        engine_databases, learner.id, confusion(theirs), proposed_by="keiko", rules=rules, now=NOW
    )
    assert outcome.reason == "evidence_not_this_learners"
    assert (await get_memory(engine_databases, learner.id, NOW)).notes == []


@pytest.mark.guardrail("memory.suppress_after_removal_days")
async def test_after_a_learner_removes_a_note_its_kind_is_held_back_for_the_suppression_window(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    evidence = await three_misses(engine_databases, learner, word)
    first = await propose_note(
        engine_databases, learner.id, confusion(evidence), proposed_by="keiko", rules=rules, now=NOW
    )
    assert first.note_id is not None
    await remove_note(engine_databases, learner.id, first.note_id, NOW)

    again = await propose_note(
        engine_databases, learner.id, confusion(evidence), proposed_by="keiko", rules=rules, now=NOW
    )
    assert again.reason == "suppressed_after_removal"

    later = NOW + timedelta(days=rules.memory.suppress_after_removal_days + 1)
    fresh = await three_misses(
        engine_databases, learner, word, days_ago=-(rules.memory.suppress_after_removal_days - 1)
    )
    after = await propose_note(
        engine_databases, learner.id, confusion(fresh), proposed_by="keiko", rules=rules, now=later
    )
    assert after.is_accepted, after.reason


@pytest.mark.guardrail("memory.max_active_notes")
async def test_a_learner_has_at_most_the_capped_number_of_active_notes(
    engine_databases: Databases, rules: Rules, learner: Learner
) -> None:
    capped = rules.model_copy(update={"memory": rules.memory.model_copy(update={"max_active_notes": 1})})
    first_word, second_word = await level_words(engine_databases, 2, 60)
    first = await three_misses(engine_databases, learner, first_word)
    second = await three_misses(engine_databases, learner, second_word)
    assert (
        await propose_note(engine_databases, learner.id, confusion(first), proposed_by="keiko", rules=capped, now=NOW)
    ).is_accepted
    refused = await propose_note(
        engine_databases, learner.id, confusion(second), proposed_by="keiko", rules=capped, now=NOW
    )
    assert refused.reason == "note_cap_reached"


async def test_the_same_evidence_cant_back_two_active_notes_of_one_kind(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    evidence = await three_misses(engine_databases, learner, word)
    await propose_note(engine_databases, learner.id, confusion(evidence), proposed_by="keiko", rules=rules, now=NOW)
    again = await propose_note(
        engine_databases,
        learner.id,
        confusion(evidence, "Kata ini sering salah dibaca."),
        proposed_by="keiko",
        rules=rules,
        now=NOW,
    )
    assert again.reason == "duplicate"


async def test_notes_the_learner_removed_or_marked_wrong_are_no_longer_remembered(
    engine_databases: Databases, rules: Rules, learner: Learner
) -> None:
    first_word, second_word = await level_words(engine_databases, 2, 80)
    removed = await propose_note(
        engine_databases,
        learner.id,
        confusion(await three_misses(engine_databases, learner, first_word)),
        proposed_by="keiko",
        rules=rules,
        now=NOW,
    )
    wrong = await propose_note(
        engine_databases,
        learner.id,
        confusion(await three_misses(engine_databases, learner, second_word)),
        proposed_by="keiko",
        rules=rules,
        now=NOW,
    )
    assert removed.note_id is not None and wrong.note_id is not None
    await remove_note(engine_databases, learner.id, removed.note_id, NOW)
    await mark_note_wrong(engine_databases, learner.id, wrong.note_id, NOW)
    assert (await get_memory(engine_databases, learner.id, NOW)).notes == []
    async with engine_databases.app.connect() as connection:
        statuses = (
            await connection.execute(
                text("SELECT status FROM learning.memory_notes WHERE learner_id = :l ORDER BY id"), {"l": learner.id}
            )
        ).scalars()
        assert list(statuses) == ["removed", "wrong"], "kept for MEM3's count, not shown or used"


async def test_a_learner_cant_change_another_learners_note(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    outcome = await propose_note(
        engine_databases,
        learner.id,
        confusion(await three_misses(engine_databases, learner, word)),
        proposed_by="keiko",
        rules=rules,
        now=NOW,
    )
    other = await create_learner(engine_databases, nickname="Lain", target_level=5)
    assert outcome.note_id is not None
    with pytest.raises(NoteNotFoundError):
        await remove_note(engine_databases, other.id, outcome.note_id, NOW)
    with pytest.raises(NoteNotFoundError):
        await mark_note_wrong(engine_databases, other.id, outcome.note_id, NOW)
    assert len((await get_memory(engine_databases, learner.id, NOW)).notes) == 1


async def test_consolidation_lapses_a_stale_note_and_records_why(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    evidence = await three_misses(engine_databases, learner, word)
    outcome = await propose_note(
        engine_databases, learner.id, confusion(evidence), proposed_by="keiko", rules=rules, now=NOW
    )
    later = NOW + timedelta(days=rules.memory.evidence_max_age_days + 1)
    [decision] = await consolidate(engine_databases.app, learner.id, rules, later)
    assert (decision.note_id, decision.decision, decision.reason) == (outcome.note_id, "lapsed", "evidence_too_old")
    assert (await get_memory(engine_databases, learner.id, later)).notes == []
    async with engine_databases.app.connect() as connection:
        recorded = (
            await connection.execute(
                text("SELECT decision, reason FROM learning.memory_consolidations WHERE learner_id = :l"),
                {"l": learner.id},
            )
        ).all()
    assert [tuple(row) for row in recorded] == [("lapsed", "evidence_too_old")]


async def test_consolidation_keeps_a_note_that_recurred_and_moves_its_evidence_date(
    engine_databases: Databases, rules: Rules, learner: Learner, word: str
) -> None:
    evidence = await three_misses(engine_databases, learner, word)
    await propose_note(engine_databases, learner.id, confusion(evidence), proposed_by="keiko", rules=rules, now=NOW)
    recurred_at = NOW + timedelta(days=20)
    await record_quiz_answer(engine_databases, learner.id, word, "reading", False, recurred_at)
    later = NOW + timedelta(days=rules.memory.evidence_max_age_days + 1)
    [decision] = await consolidate(engine_databases.app, learner.id, rules, later)
    assert (decision.decision, decision.reason) == ("kept", "recurred")
    [note] = (await get_memory(engine_databases, learner.id, later)).notes
    assert note.last_evidence_on == recurred_at.date()  # 19:00 in Jakarta, the learner's timezone: the same date


async def test_a_learner_with_no_notes_gets_an_empty_memory_that_says_so(
    engine_databases: Databases, learner: Learner
) -> None:

    memory = await get_memory(engine_databases, learner.id, NOW)
    assert memory.notes == []
    assert memory.note


async def test_marking_a_word_known_is_not_a_note(engine_databases: Databases, learner: Learner, word: str) -> None:
    """What the learner knows is recomputed from activity (MEM-R1); no agent writes it."""
    await mark_known(engine_databases, learner.id, word, NOW)
    assert (await get_memory(engine_databases, learner.id, NOW)).notes == []


@pytest.mark.guardrail("memory.allowed_categories")
async def test_the_database_refuses_a_category_the_rule_file_doesnt_allow(
    engine_databases: Databases, rules: Rules
) -> None:
    """The second wall: the table's check lists the same categories as guardrails.yaml."""
    async with engine_databases.app.connect() as connection:
        definition = str(
            await connection.scalar(
                text(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'memory_notes_category_check'"
                )
            )
        )
    for category in rules.memory.allowed_categories:
        assert f"'{category}'" in definition
    for category in rules.memory.forbidden_categories:
        assert f"'{category}'" not in definition
