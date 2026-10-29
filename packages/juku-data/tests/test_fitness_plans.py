"""FF1 and FF13: query plans and timings on a synthetic database of 5,000 learners.

The synthetic database includes one learner who knows 4,000 words (an
advanced N2 learner; N5 to N2 is about 4,700). Spike 2 timed the
per-call recommender at 231 ms p95 for such a learner, which is why the
candidates are now kept incrementally.
"""

import json
import time
from collections.abc import AsyncIterator, Iterator
from datetime import date, datetime, timedelta
from typing import Any

import pytest
from juku_common.rules import Rules
from juku_data.engine import Databases, get_learner, recommend_words
from juku_data.engine.models import Learner
from juku_data.engine.plans import HOT_QUERIES, HotQuery
from juku_data.engine.reads import known_word_ids
from juku_data.engine.recompute import EXPECTED_ACTIVITY, EXPECTED_STATE
from juku_data.synthetic import HEAVY_LEARNER_KNOWN_WORDS, HEAVY_LEARNER_PUBLIC_ID
from juku_testkit.databases import TestDatabase
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Building the synthetic database takes a minute or two the first time; it's then kept.
pytestmark = pytest.mark.timeout(900)

WARM_UP_RUNS = 3
TIMED_RUNS = 10


@pytest.fixture
async def synthetic(synthetic_database: TestDatabase, dict_engine: AsyncEngine) -> AsyncIterator[Databases]:
    app = create_async_engine(synthetic_database.sqlalchemy_url)
    try:
        yield Databases(app=app, dictionary=dict_engine)
    finally:
        await app.dispose()


@pytest.fixture
async def heavy(synthetic: Databases) -> Learner:
    return await get_learner(synthetic, HEAVY_LEARNER_PUBLIC_ID)


async def parameters_for(db: Databases, learner: Learner) -> dict[str, Any]:
    today = date(2026, 12, 1)
    return {
        "learner_id": learner.id,
        "learner_ids": [learner.id],
        "target_level": learner.target_level,
        "limit": 10,
        "known": await known_word_ids(db.app, learner.id),
        "end_of_day": datetime(2026, 12, 2),
        "first_excluded": today - timedelta(days=7),
        "today": today,
    }


async def explain(engine: AsyncEngine, sql: str, parameters: dict[str, Any]) -> dict[str, Any]:
    async with engine.connect() as connection:
        plan = await connection.scalar(text(f"EXPLAIN (FORMAT JSON) {sql}"), parameters)
    parsed: Any = json.loads(plan) if isinstance(plan, str) else plan
    return parsed[0]["Plan"]


def nodes(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from nodes(child)


async def test_the_heavy_learner_knows_at_least_4000_words(synthetic: Databases, heavy: Learner) -> None:
    # 4,000 marked known, plus the few its quiz answers taught it.
    assert len(await known_word_ids(synthetic.app, heavy.id)) >= HEAVY_LEARNER_KNOWN_WORDS


@pytest.mark.fitness("FF1")
async def test_recommend_words_for_the_4000_word_learner_is_under_the_limit(
    synthetic: Databases, heavy: Learner, rules: Rules
) -> None:
    for _ in range(WARM_UP_RUNS):
        await recommend_words(synthetic, heavy.id)
    timings: list[float] = []
    words = []
    for _ in range(TIMED_RUNS):
        started = time.perf_counter()
        words = (await recommend_words(synthetic, heavy.id)).words
        timings.append((time.perf_counter() - started) * 1000)
    assert len(words) == 10
    assert max(timings) <= rules.threshold("FF1", "recommend_words_max_ms"), f"timings (ms): {timings}"


@pytest.mark.fitness("FF1")
@pytest.mark.parametrize("query", HOT_QUERIES, ids=lambda q: q.name)
async def test_each_hot_query_stays_under_its_recorded_cost_ceiling(
    synthetic: Databases, heavy: Learner, rules: Rules, query: HotQuery
) -> None:
    engine = synthetic.app if query.database == "app" else synthetic.dictionary
    plan = await explain(engine, query.sql, await parameters_for(synthetic, heavy))
    assert plan["Total Cost"] <= rules.threshold("FF1", f"cost_{query.name}")


@pytest.mark.fitness("FF1")
@pytest.mark.parametrize("sql", [EXPECTED_STATE, EXPECTED_ACTIVITY], ids=["state", "activity"])
async def test_a_one_learner_recompute_never_scans_a_large_event_partition(
    synthetic: Databases, heavy: Learner, rules: Rules, sql: str
) -> None:
    plan = await explain(synthetic.app, sql, await parameters_for(synthetic, heavy))
    limit = rules.threshold("FF1", "max_event_seq_scan_rows")
    scans = [
        (node.get("Relation Name"), node["Plan Rows"])
        for node in nodes(plan)
        if node["Node Type"] == "Seq Scan"
        and str(node.get("Relation Name", "")).startswith("learning_events")
        and node["Plan Rows"] > limit
    ]
    assert scans == []


@pytest.mark.fitness("FF13")
async def test_the_mcp_role_runs_with_jit_off(synthetic: Databases) -> None:
    async with synthetic.app.connect() as connection:
        settings = await connection.scalar(text("SELECT rolconfig FROM pg_roles WHERE rolname = 'juku_mcp'"))
    assert "jit=off" in list(settings or [])


@pytest.mark.fitness("FF13")
@pytest.mark.parametrize("query", [q for q in HOT_QUERIES if q.is_tool_query], ids=lambda q: q.name)
async def test_each_tool_query_stays_below_the_jit_threshold(
    synthetic: Databases, heavy: Learner, rules: Rules, query: HotQuery
) -> None:
    engine = synthetic.app if query.database == "app" else synthetic.dictionary
    plan = await explain(engine, query.sql, await parameters_for(synthetic, heavy))
    assert plan["Total Cost"] < rules.threshold("FF13", "jit_above_cost")
