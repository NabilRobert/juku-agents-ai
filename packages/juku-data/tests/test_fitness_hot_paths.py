"""FF2: the $0 pages and the agents' tools read summaries only, never the event history."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fixture_learners import FixtureLearner
from juku_data.engine import (
    Databases,
    find_reading_sentences,
    get_mistakes,
    get_plan,
    get_progress,
    get_recent_activity,
    make_quiz,
    rebuild_learner,
    recommend_words,
)
from juku_data.engine.models import Learner
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the engine lands in the next commits")

EVENT_TABLE = "learning_events"


class QueryLog:
    """Every statement an engine sends, recorded through SQLAlchemy's events."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine.sync_engine
        self.statements: list[str] = []

    def _record(self, *args: Any) -> None:
        self.statements.append(str(args[2]))

    def __enter__(self) -> "QueryLog":
        event.listen(self.engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *_: object) -> None:
        event.remove(self.engine, "before_cursor_execute", self._record)

    def touched_events(self) -> bool:
        return any(EVENT_TABLE in statement for statement in self.statements)


@pytest.fixture
def budi(fixtures_and_learners: dict[str, tuple[FixtureLearner, Learner]]) -> Iterator[Learner]:
    yield fixtures_and_learners["budi"][1]


READS = {
    "get_progress": lambda db, learner: get_progress(db, learner.id),
    "get_mistakes": lambda db, learner: get_mistakes(db, learner.id, datetime(2026, 11, 8, tzinfo=UTC)),
    "recommend_words": lambda db, learner: recommend_words(db, learner.id),
    "find_reading_sentences": lambda db, learner: find_reading_sentences(db, learner.id),
    "get_plan": lambda db, learner: get_plan(db, learner.id, date(2026, 11, 8)),
    "get_recent_activity": lambda db, learner: get_recent_activity(db, learner.id, date(2026, 11, 8)),
    "make_quiz": lambda db, learner: make_quiz(db, learner.id, date(2026, 11, 8)),
}


@pytest.mark.fitness("FF2")
@pytest.mark.parametrize("name", sorted(READS))
async def test_a_read_touches_only_the_summaries(engine_databases: Databases, budi: Learner, name: str) -> None:
    with QueryLog(engine_databases.app) as log:
        await READS[name](engine_databases, budi)
    assert log.statements, "the log recorded nothing: the probe is broken"
    assert not log.touched_events(), f"{name} read {EVENT_TABLE}"


@pytest.mark.fitness("FF2")
async def test_the_probe_does_see_a_function_that_reads_the_events(engine_databases: Databases, budi: Learner) -> None:
    with QueryLog(engine_databases.app) as log:
        await rebuild_learner(engine_databases, budi.id)
    assert log.touched_events()
