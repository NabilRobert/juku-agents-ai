"""The weekly run (ADR-007, ADR-014; AG1 to AG4): revisions, idempotency (FF7), the budget and notes."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from juku_app.pipeline.crew import KEIKO_INSTRUCTIONS, NIKKI_INSTRUCTIONS
from juku_app.pipeline.facts import WeekFacts
from juku_app.pipeline.run import run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_testkit.memory_fixtures import load_memory_fixture
from pipeline_helpers import (
    approving_tadashi,
    consented,
    crew_of,
    faithful_keiko,
    faithful_nikki,
    faithful_plan,
    fixture_learner,
    prompt_of,
    reports_of,
    scalar,
    services_for,
    structured,
    sunday_evening,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo
from sqlalchemy import text


async def fallback_reason_of(db: Databases, run_id: int | None) -> str | None:
    return await scalar(db, "SELECT fallback_reason FROM app.pipeline_runs WHERE id = :id", id=run_id)


# --- revisions (AG1) ---


@pytest.mark.guardrail("pipeline.max_revisions")
async def test_an_output_tadashi_flags_is_revised_with_the_issues_and_then_published(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)
    nikki_prompts: list[dict[str, Any]] = []
    reviews_of_nikki = iter(
        [{"grade": "C", "issues": [{"reason": "Terlalu kaku.", "severity": "high"}], "feedback": "Lebih hangat."}]
    )

    def nikki(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nikki_prompts.append(prompt_of(messages))
        return faithful_nikki(messages, info)

    def tadashi(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if prompt_of(messages)["author"] == "nikki":
            return structured(info, next(reviews_of_nikki, {"grade": "A", "issues": [], "feedback": ""}))
        return approving_tadashi(messages, info)

    outcome = await run_weekly(
        services_for(engine_databases, rules, crew_of(nikki=nikki, tadashi=tadashi)),
        learner,
        sunday_evening(learner.timezone),
    )
    assert outcome.status == "published"
    assert len(nikki_prompts) == 2
    assert nikki_prompts[1]["revision"]["issues"][0]["reason"] == "Terlalu kaku."
    assert nikki_prompts[1]["revision"]["feedback"] == "Lebih hangat."


# --- FF7: idempotent per (learner, week) ---


@pytest.mark.fitness("FF7")
async def test_a_rerun_after_a_published_report_publishes_nothing_more(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)
    services = services_for(engine_databases, rules, crew_of())
    now = sunday_evening(learner.timezone)
    first = await run_weekly(services, learner, now)
    again = await run_weekly(services, learner, now + timedelta(hours=1))
    assert (first.status, again.status, again.run_id) == ("published", "skipped", first.run_id)
    assert await reports_of(engine_databases, learner) == 1


@pytest.mark.fitness("FF7")
@pytest.mark.guardrail("pipeline.run_lease_minutes")
async def test_a_run_killed_midway_is_taken_over_after_its_lease_and_publishes_once(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)
    now = sunday_evening(learner.timezone)

    def dying_nikki(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise RuntimeError("the worker was killed")

    with pytest.raises(RuntimeError):
        await run_weekly(services_for(engine_databases, rules, crew_of(nikki=dying_nikki)), learner, now)
    healthy = services_for(engine_databases, rules, crew_of())
    during_lease = await run_weekly(healthy, learner, now + timedelta(minutes=rules.pipeline.run_lease_minutes - 1))
    assert during_lease.status == "busy"
    after_lease = await run_weekly(healthy, learner, now + timedelta(minutes=rules.pipeline.run_lease_minutes + 1))
    assert after_lease.status == "published"
    assert after_lease.run_id == during_lease.run_id
    assert await reports_of(engine_databases, learner) == 1


# --- the budget (B1): reports have their own pool ---


async def test_with_the_reports_pool_spent_the_learner_still_gets_the_facts_only_report(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)

    def never(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise AssertionError("no model may be called once the pool is spent")

    async with engine_databases.app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.model_calls (called_at, pool, requests, input_tokens, cached_input_tokens, "
                "output_tokens, cost_usd) VALUES (now(), 'reports', 1, 0, 0, 0, :cost)"
            ),
            {"cost": rules.budget.reports_pool_usd},
        )
    try:
        outcome = await run_weekly(
            services_for(engine_databases, rules, crew_of(keiko=never, nikki=never, tadashi=never)),
            learner,
            sunday_evening(learner.timezone),
        )
        assert outcome.status == "fallback"
        assert await fallback_reason_of(engine_databases, outcome.run_id) == "budget_spent"
    finally:
        async with engine_databases.app.begin() as connection:
            await connection.execute(text("DELETE FROM app.model_calls WHERE pool = 'reports'"))


async def test_each_agent_call_is_recorded_against_the_reports_pool(engine_databases: Databases, rules: Rules) -> None:
    learner = await fixture_learner(engine_databases, rules)
    await run_weekly(services_for(engine_databases, rules, crew_of()), learner, sunday_evening(learner.timezone))
    calls = await scalar(
        engine_databases,
        "SELECT count(*) FROM app.model_calls WHERE pool = 'reports' AND learner_id = :l",
        l=learner.id,
    )
    assert calls == 4  # Keiko, Tadashi on the plan, Nikki, Tadashi on the report


async def test_a_model_that_cant_give_a_valid_plan_ends_in_the_facts_only_report(
    engine_databases: Databases, rules: Rules
) -> None:
    """Without a model key, the app's stand-in model answers in plain text: the learner still gets a report."""
    learner = await fixture_learner(engine_databases, rules)

    def chatty(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart("Maaf, belum tersedia.")])

    outcome = await run_weekly(
        services_for(engine_databases, rules, crew_of(keiko=chatty)), learner, sunday_evening(learner.timezone)
    )
    assert outcome.status == "fallback"
    assert await fallback_reason_of(engine_databases, outcome.run_id) == "output_refused"


async def test_a_plan_sent_back_every_time_is_recorded_as_not_approved(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)

    def strict(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return structured(info, {"grade": "D", "issues": [{"reason": "Kurang.", "severity": "high"}], "feedback": ""})

    outcome = await run_weekly(
        services_for(engine_databases, rules, crew_of(tadashi=strict)), learner, sunday_evening(learner.timezone)
    )
    assert outcome.status == "fallback"
    assert await fallback_reason_of(engine_databases, outcome.run_id) == "not_approved"


async def test_a_published_run_has_no_fallback_reason(engine_databases: Databases, rules: Rules) -> None:
    learner = await fixture_learner(engine_databases, rules)
    outcome = await run_weekly(
        services_for(engine_databases, rules, crew_of()), learner, sunday_evening(learner.timezone)
    )
    assert outcome.status == "published"
    assert await fallback_reason_of(engine_databases, outcome.run_id) is None


# --- memory: Keiko's proposals go through juku_data.memory (MEM-R2) ---


async def test_an_approved_plans_note_proposals_are_checked_and_stored_as_keikos(
    engine_databases: Databases, rules: Rules
) -> None:
    loaded = await load_memory_fixture(
        engine_databases, rules, "nur", suffix=f"-{uuid.uuid4().hex[:6]}", source="pipeline"
    )
    await consented(engine_databases, loaded.learner)

    def keiko(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        plan = faithful_plan(prompt_of(messages)["facts"])
        plan["note_proposals"] = [
            {
                "category": "recurring_confusion",
                "text": "Sering salah arti kata hewan.",
                "evidence_event_ids": [loaded.event_ids["m1"], loaded.event_ids["m2"], loaded.event_ids["m3"]],
            }
        ]
        return structured(info, plan)

    await run_weekly(
        services_for(engine_databases, rules, crew_of(keiko=keiko)), loaded.learner, sunday_evening("Asia/Jayapura")
    )
    refused = await scalar(
        engine_databases,
        "SELECT reason FROM learning.memory_note_rejections WHERE learner_id = :l",
        l=loaded.learner.id,
    )
    assert refused == "evidence_does_not_show_pattern", (
        "two kinds of quiz don't show one confusion: memory's rules apply"
    )


# --- what the agents are told (paid run 2: made-up note categories, citations of fields) ---


async def test_keiko_and_her_reviewer_are_shown_the_allowed_note_categories_by_name(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules)
    shown: dict[str, Any] = {}

    def keiko(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        shown["keiko"] = prompt_of(messages)["note_categories"]
        return faithful_keiko(messages, info)

    def tadashi(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        sent = prompt_of(messages)
        if sent["author"] == "keiko":
            shown["tadashi"] = sent["given"]["note_categories"]
        return approving_tadashi(messages, info)

    await run_weekly(
        services_for(engine_databases, rules, crew_of(keiko=keiko, tadashi=tadashi)),
        learner,
        sunday_evening(learner.timezone),
    )
    assert shown == {"keiko": rules.memory.allowed_categories, "tadashi": rules.memory.allowed_categories}


@pytest.mark.parametrize("instructions", [KEIKO_INSTRUCTIONS, NIKKI_INSTRUCTIONS], ids=["keiko", "nikki"])
def test_the_writers_instructions_name_every_citable_field(instructions: str) -> None:
    for field in WeekFacts.model_fields:
        assert field in instructions
