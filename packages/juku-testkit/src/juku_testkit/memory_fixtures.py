"""MEM1's fixture learners (evals/memory/learners/*.yaml), replayed into a test database.

A fixture lists a learner's activity, the notes agents proposed, and what
the learner and the weekly consolidation did afterwards. `load_memory_fixture`
replays all of it, in time order, through the same code production uses:
the engine's write functions for activity, and juku_data.memory for the
notes. Each proposal's outcome must be the one the fixture expects, so a
fixture can't silently drift from the rules it illustrates.

Events are named by `label`, and proposals cite their evidence by label;
words are `spelling/reading`, resolved against the loaded dictionary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import yaml
from juku_common.rules import Rules
from juku_data.engine import Databases, create_learner, mark_known, record_sentence_read, unmark_known
from juku_data.engine.api import record_quiz_answer
from juku_data.engine.models import Learner, QuizKind
from juku_data.memory import NoteProposal, consolidate, mark_note_wrong, propose_note, remove_note
from sqlalchemy import text

from juku_testkit.databases import repo_root

MEMORY_EVALS = repo_root() / "evals" / "memory"
QUIZ_KINDS: dict[str, QuizKind] = {"quiz_meaning": "meaning", "quiz_reading": "reading"}
ACCEPTED = "accepted"


@dataclass
class LoadedFixture:
    name: str
    learner: Learner
    event_ids: dict[str, int] = field(default_factory=dict[str, int])
    note_ids: list[int | None] = field(default_factory=list[int | None])


def load_suite() -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load((MEMORY_EVALS / "suite.yaml").read_text(encoding="utf-8")))


def fixture_now() -> datetime:
    return datetime.fromisoformat(str(load_suite()["fixture"]["now"]))


def _read(name: str) -> dict[str, Any]:
    path: Path = MEMORY_EVALS / "learners" / f"{name}.yaml"
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


async def _word_id(db: Databases, spelling_and_reading: str) -> str:
    spelling, reading = spelling_and_reading.split("/")
    async with db.dictionary.connect() as connection:
        found = list(
            await connection.scalars(
                text("SELECT id FROM ojlpt.vocab WHERE word = :word AND reading = :reading"),
                {"word": spelling, "reading": reading},
            )
        )
    if len(found) != 1:
        raise ValueError(f"fixture word {spelling_and_reading} matches {len(found)} words; it must match one")
    return str(found[0])


async def _latest_event_id(db: Databases, learner_id: int) -> int:
    async with db.app.connect() as connection:
        found = await connection.scalar(
            text("SELECT max(id) FROM learning.learning_events WHERE learner_id = :learner"), {"learner": learner_id}
        )
    return int(found)


async def _replay_event(db: Databases, learner: Learner, item: dict[str, Any], at: datetime) -> None:
    kind = str(item["type"])
    if kind == "sentence_read":
        await record_sentence_read(db, learner.id, int(item["sentence"]), at)
        return
    word_id = await _word_id(db, str(item["word"]))
    if kind == "marked_known":
        await mark_known(db, learner.id, word_id, at)
    elif kind == "unmarked_known":
        await unmark_known(db, learner.id, word_id, at)
    elif kind in QUIZ_KINDS:
        await record_quiz_answer(db, learner.id, word_id, QUIZ_KINDS[kind], bool(item["correct"]), at)
    else:
        raise ValueError(f"unknown fixture event type {kind!r}")


async def _replay_proposal(
    db: Databases, rules: Rules, loaded: LoadedFixture, item: dict[str, Any], at: datetime
) -> None:
    proposal = NoteProposal(
        category=str(item["category"]),
        text=str(item["text"]),
        evidence_event_ids=[loaded.event_ids[label] for label in item["evidence"]],
    )
    outcome = await propose_note(db, loaded.learner.id, proposal, proposed_by=str(item["by"]), rules=rules, now=at)
    actual = ACCEPTED if outcome.is_accepted else str(outcome.reason)
    if actual != item["expect"]:
        raise AssertionError(
            f"{loaded.name}: proposal {item['text']!r} was {actual}, the fixture expects {item['expect']}"
        )
    loaded.note_ids.append(outcome.note_id)


async def _replay_action(
    db: Databases, rules: Rules, loaded: LoadedFixture, item: dict[str, Any], at: datetime
) -> None:
    learner_id = loaded.learner.id
    if "remove" in item:
        await remove_note(db, learner_id, _note(loaded, int(item["remove"])), at)
    elif "mark_wrong" in item:
        await mark_note_wrong(db, learner_id, _note(loaded, int(item["mark_wrong"])), at)
    elif item.get("consolidate"):
        await consolidate(db, learner_id, rules, at)
    else:
        raise ValueError(f"unknown fixture action {item!r}")


def _note(loaded: LoadedFixture, index: int) -> int:
    note_id = loaded.note_ids[index]
    if note_id is None:
        raise ValueError(f"{loaded.name}: action names proposal {index}, which was rejected")
    return note_id


async def load_memory_fixture(db: Databases, rules: Rules, name: str, *, suffix: str = "") -> LoadedFixture:
    """Create the learner and replay its events, proposals and actions in time order."""
    raw = _read(name)
    learner = await create_learner(
        db,
        nickname=str(raw["nickname"]),
        target_level=int(raw["target_level"]),
        timezone=str(raw["timezone"]),
        public_id=str(raw["public_id"]) + suffix,
    )
    loaded = LoadedFixture(name=name, learner=learner)
    steps: list[tuple[datetime, int, str, dict[str, Any]]] = []
    for kind in ("events", "proposals", "actions"):
        for item in cast(list[dict[str, Any]], raw.get(kind) or []):
            steps.append((datetime.fromisoformat(str(item["at"])), len(steps), kind, item))
    for at, _, kind, item in sorted(steps):
        if kind == "events":
            await _replay_event(db, learner, item, at)
            loaded.event_ids[str(item["label"])] = await _latest_event_id(db, learner.id)
        elif kind == "proposals":
            await _replay_proposal(db, rules, loaded, item, at)
        else:
            await _replay_action(db, rules, loaded, item, at)
    return loaded
