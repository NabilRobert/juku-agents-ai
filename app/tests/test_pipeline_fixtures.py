"""The weekly pipeline on its 10 fixture learners (evals/pipeline/), with a scripted crew ($0).

For each learner: the facts code gathers match the gold from SQL; a
faithful crew's report is approved and published as written. For each
planted bad output (planted.yaml), Tadashi is scripted to approve it, and
code blocks it anyway; after 2 revisions the learner gets the facts-only
report (slice 6's "Done when").
"""

import uuid
from typing import Any, cast

import pytest
import yaml
from juku_app.pipeline.facts import gather_facts
from juku_app.pipeline.fallback import facts_only_report
from juku_app.pipeline.run import run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_testkit.memory_fixtures import PIPELINE_EVALS, LoadedFixture, load_memory_fixture
from pipeline_helpers import (
    consented,
    crew_of,
    faithful_report,
    planted_keiko,
    planted_nikki,
    services_for,
    sunday_evening,
)
from sqlalchemy import text

FIXTURES = cast(dict[str, Any], yaml.safe_load((PIPELINE_EVALS / "fixtures.yaml").read_text(encoding="utf-8")))
PLANTED = cast(dict[str, Any], yaml.safe_load((PIPELINE_EVALS / "planted.yaml").read_text(encoding="utf-8")))
LEARNERS = {str(item["name"]): item for item in FIXTURES["learners"]}
CASES = {str(case["id"]): case for case in PLANTED["cases"]}
SOURCE_OF = {name: str(item["source"]) for name, item in LEARNERS.items()}


async def load(db: Databases, rules: Rules, name: str) -> LoadedFixture:
    loaded = await load_memory_fixture(db, rules, name, suffix=f"-{uuid.uuid4().hex[:6]}", source=SOURCE_OF[name])
    await consented(db, loaded.learner)
    return loaded


def test_there_are_fixtures_for_ten_learners() -> None:
    assert len(LEARNERS) == 10


@pytest.mark.parametrize("name", sorted(LEARNERS))
async def test_the_facts_match_the_gold_from_sql(engine_databases: Databases, rules: Rules, name: str) -> None:
    loaded = await load(engine_databases, rules, name)
    facts = await gather_facts(engine_databases, loaded.learner, sunday_evening(loaded.learner.timezone))
    assert (str(facts.week_start), str(facts.week_end)) == (
        FIXTURES["fixture"]["week_start"],
        FIXTURES["fixture"]["week_end"],
    )
    async with engine_databases.app.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(FIXTURES["reference_sql"]),
                    {"learner_id": loaded.learner.id, "week_start": facts.week_start, "week_end": facts.week_end},
                )
            )
            .mappings()
            .one()
        )
    gold = {column: int(value) for column, value in row.items()}
    assert gold == LEARNERS[name]["expected"], "the fixture's gold no longer matches its SQL"
    gathered = {
        "known_words": facts.progress.known_words,
        "quiz_answers": facts.activity.quiz_answers,
        "quiz_correct": facts.activity.quiz_correct,
        "words_marked": facts.activity.words_marked,
        "sentences_read": facts.activity.sentences_read,
        "mistakes": len(facts.mistakes.items),
        "notes": len(facts.memory.notes),
    }
    assert gathered == gold


@pytest.mark.parametrize("name", sorted(LEARNERS))
async def test_a_faithful_crews_report_is_published_as_written(
    engine_databases: Databases, rules: Rules, name: str
) -> None:
    loaded = await load(engine_databases, rules, name)
    now = sunday_evening(loaded.learner.timezone)
    outcome = await run_weekly(services_for(engine_databases, rules, crew_of()), loaded.learner, now)
    facts = await gather_facts(engine_databases, loaded.learner, now)
    assert outcome.status == "published"
    from pipeline_helpers import faithful_plan

    expected = faithful_report(facts.model_dump(mode="json"), faithful_plan(facts.model_dump(mode="json")))
    assert outcome.report == expected
    async with engine_databases.app.connect() as connection:
        stored = (
            await connection.execute(
                text("SELECT body, is_fallback FROM app.reports WHERE learner_id = :l"), {"l": loaded.learner.id}
            )
        ).all()
    assert [tuple(row) for row in stored] == [(expected, False)]


def fill(value: Any, slots: dict[str, Any]) -> Any:
    """The planted output with its placeholders filled in (planted.yaml's header)."""
    if isinstance(value, str):
        for slot, filled in slots.items():
            if value == "{" + slot + "}":
                return filled
            value = value.replace("{" + slot + "}", str(filled))
        return value
    if isinstance(value, list):
        return [fill(item, slots) for item in cast(list[Any], value)]
    if isinstance(value, dict):
        return {key: fill(item, slots) for key, item in cast(dict[str, Any], value).items()}
    return value


async def slots_for(db: Databases, loaded: LoadedFixture) -> dict[str, Any]:
    facts = await gather_facts(db, loaded.learner, sunday_evening(loaded.learner.timezone))
    async with db.app.connect() as connection:
        known = await connection.scalar(
            text(
                "SELECT item_id FROM learning.learner_state WHERE learner_id = :l AND is_known ORDER BY item_id LIMIT 1"
            ),
            {"l": loaded.learner.id},
        )
        removed = await connection.scalar(
            text("SELECT id FROM learning.memory_notes WHERE learner_id = :l AND status = 'removed' LIMIT 1"),
            {"l": loaded.learner.id},
        )
    first = facts.candidates.words[0]
    return {
        "known_word": str(known),
        "removed_note": f"note-{removed}",
        "first_candidate": first.word_id,
        "wrong_level": 1 if first.level != 1 else 2,
    }


@pytest.mark.parametrize("case_id", sorted(CASES))
async def test_a_planted_bad_output_is_blocked_in_code_and_the_facts_only_report_goes_out(
    engine_databases: Databases, rules: Rules, case_id: str
) -> None:
    case = CASES[case_id]
    loaded = await load(engine_databases, rules, str(case["learner"]))
    now = sunday_evening(loaded.learner.timezone)
    slots = await slots_for(engine_databases, loaded)
    if case["stage"] == "keiko":
        crew = crew_of(keiko=planted_keiko(fill(case["plan"], slots)))
    else:
        crew = crew_of(nikki=planted_nikki(fill(case["output"], slots)))

    outcome = await run_weekly(services_for(engine_databases, rules, crew), loaded.learner, now)

    facts = await gather_facts(engine_databases, loaded.learner, now)
    assert outcome.status == "fallback"
    assert outcome.report == facts_only_report(facts)
    async with engine_databases.app.connect() as connection:
        reviews = (
            await connection.execute(
                text(
                    "SELECT r.code_issues FROM app.critic_reviews r JOIN app.pipeline_runs p ON p.id = r.run_id "
                    "WHERE p.learner_id = :l AND r.agent = :agent ORDER BY r.id"
                ),
                {"l": loaded.learner.id, "agent": case["stage"]},
            )
        ).scalars()
        kinds = [{issue["kind"] for issue in issues} for issues in reviews]
    assert len(kinds) == 1 + rules.pipeline.max_revisions
    assert all(case["expect"] in found for found in kinds), kinds


@pytest.mark.parametrize("name", sorted(LEARNERS))
async def test_the_facts_only_report_passes_codes_own_checks(
    engine_databases: Databases, rules: Rules, name: str
) -> None:
    """The fallback can't be blocked: every number is a fact, every sentence cites its section."""
    from juku_app.pipeline.checks import check_report

    loaded = await load(engine_databases, rules, name)
    facts = await gather_facts(engine_databases, loaded.learner, sunday_evening(loaded.learner.timezone))
    assert check_report(facts_only_report(facts), facts, facts, rules) == []
