"""The fixture learners (Phase 1 E1): event scripts in tests/fixtures/learners/*.yaml.

A script names words as `spelling/reading` and may mark "the first N words
of a level" (by commonness, then ID) in one line. `load_fixture` resolves
them against the loaded dictionary; `replay` feeds the events, in time
order, through the engine's own write functions; `known_words` folds them
with LE1's rule, independently of the engine, for the oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast
from zoneinfo import ZoneInfo

import yaml
from juku_data.engine import Databases, create_learner, mark_known, record_sentence_read, unmark_known
from juku_data.engine.api import record_quiz_answer
from juku_data.engine.models import Learner, QuizKind
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

FIXTURES = Path(__file__).parent / "fixtures"
LEARNERS = FIXTURES / "learners"
EXPECTED = FIXTURES / "expected"
FIXTURE_NAMES = sorted(path.stem for path in LEARNERS.glob("*.yaml"))
QUIZ_KINDS: dict[str, QuizKind] = {"quiz_meaning": "meaning", "quiz_reading": "reading"}


@dataclass(frozen=True)
class FixtureEvent:
    at: datetime
    type: str
    word_id: str | None = None
    is_correct: bool | None = None
    sentence_id: int | None = None


@dataclass(frozen=True)
class FixtureLearner:
    name: str
    public_id: str
    target_level: int
    timezone: str
    exam_date: date | None
    events: list[FixtureEvent]


async def word_id_of(dict_engine: AsyncEngine, spelling_and_reading: str) -> str:
    spelling, reading = spelling_and_reading.split("/")
    async with dict_engine.connect() as connection:
        found = list(
            await connection.scalars(
                text("SELECT id FROM ojlpt.vocab WHERE word = :word AND reading = :reading"),
                {"word": spelling, "reading": reading},
            )
        )
    if len(found) != 1:
        raise ValueError(f"fixture word {spelling_and_reading} matches {len(found)} words; it must match one")
    return str(found[0])


async def first_words(dict_engine: AsyncEngine, count: int, level: int) -> list[str]:
    async with dict_engine.connect() as connection:
        found = await connection.scalars(
            text("SELECT id FROM ojlpt.word_level WHERE level = :level ORDER BY commonness, id LIMIT :count"),
            {"level": level, "count": count},
        )
        return [str(word_id) for word_id in found]


async def load_fixture(dict_engine: AsyncEngine, name: str) -> FixtureLearner:
    raw = cast(dict[str, Any], yaml.safe_load((LEARNERS / f"{name}.yaml").read_text(encoding="utf-8")))
    events: list[FixtureEvent] = []
    for item in cast(list[dict[str, Any]], raw["events"]):
        at = datetime.fromisoformat(str(item["at"]))
        if "first" in item:
            for word_id in await first_words(dict_engine, int(item["first"]), int(item["level"])):
                events.append(FixtureEvent(at, item["type"], word_id=word_id))
        elif "word" in item:
            word_id = await word_id_of(dict_engine, str(item["word"]))
            events.append(FixtureEvent(at, item["type"], word_id=word_id, is_correct=item.get("correct")))
        else:
            events.append(FixtureEvent(at, item["type"], sentence_id=int(item["sentence"])))
    marked = [event.word_id for event in events if event.type == "marked_known"]
    if len(marked) != len(set(marked)):
        raise ValueError(f"fixture {name} marks a word known twice; make each event's word distinct")
    exam = raw.get("exam_date")
    return FixtureLearner(
        name=name,
        public_id=str(raw["public_id"]),
        target_level=int(raw["target_level"]),
        timezone=str(raw["timezone"]),
        exam_date=exam if isinstance(exam, date) else None,
        events=sorted(events, key=lambda event: event.at),  # stable: same-time events keep file order
    )


async def replay(db: Databases, fixture: FixtureLearner, *, suffix: str = "") -> Learner:
    """Create the learner and feed its events, in time order, through the engine."""
    learner = await create_learner(
        db,
        nickname=fixture.name,
        target_level=fixture.target_level,
        timezone=fixture.timezone,
        exam_date=fixture.exam_date,
        public_id=fixture.public_id + suffix,
    )
    for event in fixture.events:
        if event.type == "marked_known" and event.word_id:
            await mark_known(db, learner.id, event.word_id, event.at)
        elif event.type == "unmarked_known" and event.word_id:
            await unmark_known(db, learner.id, event.word_id, event.at)
        elif event.type in QUIZ_KINDS and event.word_id and event.is_correct is not None:
            await record_quiz_answer(db, learner.id, event.word_id, QUIZ_KINDS[event.type], event.is_correct, event.at)
        elif event.type == "sentence_read" and event.sentence_id is not None:
            await record_sentence_read(db, learner.id, event.sentence_id, event.at)
        else:
            raise ValueError(f"fixture {fixture.name}: can't replay {event}")
    return learner


def known_words(fixture: FixtureLearner) -> set[str]:
    """LE1, folded by hand: marked, or correct on two local days, counting only since the last unmark."""
    zone = ZoneInfo(fixture.timezone)
    marked: set[str] = set()
    correct_days: dict[str, set[date]] = {}
    for event in fixture.events:
        if event.word_id is None:
            continue
        if event.type == "marked_known":
            marked.add(event.word_id)
        elif event.type == "unmarked_known":
            marked.discard(event.word_id)
            correct_days.pop(event.word_id, None)
        elif event.type in QUIZ_KINDS and event.is_correct:
            correct_days.setdefault(event.word_id, set()).add(event.at.astimezone(zone).date())
    return marked | {word_id for word_id, days in correct_days.items() if len(days) >= 2}
