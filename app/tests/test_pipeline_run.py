"""The weekly run (ADR-007, ADR-014; AG1 to AG4): revisions, idempotency (FF7), budget, schedule, replans, records."""

import json
import uuid
from datetime import timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.invites import issue_codes
from juku_app.pipeline.crew import CrewModels, build_crew, keiko_toolset
from juku_app.pipeline.feedback import draft_feedback
from juku_app.pipeline.run import due_learners, run_due, run_replans, run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from juku_testkit.memory_fixtures import load_memory_fixture
from pipeline_helpers import (
    approving_tadashi,
    consented,
    crew_of,
    faithful_keiko,
    faithful_nikki,
    faithful_plan,
    prompt_of,
    services_for,
    structured,
    sunday_evening,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import text
from web_helpers import client_for, csrf_of, deps, sign_up


async def fixture_learner(db: Databases, rules: Rules, name: str = "joko") -> Learner:
    source = "memory" if name in {"fajar", "gita", "hana", "indra"} else "pipeline"
    loaded = await load_memory_fixture(db, rules, name, suffix=f"-{uuid.uuid4().hex[:6]}", source=source)
    return await consented(db, loaded.learner)


async def scalar(db: Databases, sql: str, **parameters: Any) -> Any:
    async with db.app.connect() as connection:
        return await connection.scalar(text(sql), parameters)


async def reports_of(db: Databases, learner: Learner) -> int:
    return int(await scalar(db, "SELECT count(*) FROM app.reports WHERE learner_id = :l", l=learner.id))


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


# --- the schedule (AG2): Sunday 18:00 in each learner's own timezone ---


@pytest.mark.guardrail("pipeline.due_weekday")
@pytest.mark.guardrail("pipeline.due_hour")
async def test_a_learner_is_due_at_sunday_six_pm_in_their_own_timezone(
    engine_databases: Databases, rules: Rules
) -> None:
    jakarta = await fixture_learner(engine_databases, rules, "joko")
    tokyo = await fixture_learner(engine_databases, rules, "kartika")
    at_jakarta_six = sunday_evening("Asia/Jakarta")  # 20:00 in Tokyo: due there too (since 18:00)
    at_tokyo_six = sunday_evening("Asia/Tokyo")  # 16:00 in Jakarta: not yet
    due_then = {learner.id for learner in await due_learners(engine_databases, rules, at_jakarta_six)}
    due_earlier = {learner.id for learner in await due_learners(engine_databases, rules, at_tokyo_six)}
    assert {jakarta.id, tokyo.id} <= due_then
    assert tokyo.id in due_earlier and jakarta.id not in due_earlier


async def test_the_hourly_job_runs_each_due_learner_once_and_records_itself(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules, "lestari")
    services = services_for(engine_databases, rules, crew_of())
    now = sunday_evening("Asia/Jakarta")
    await run_due(services, engine_databases.app, now)
    await run_due(services, engine_databases.app, now + timedelta(hours=1))
    assert await reports_of(engine_databases, learner) == 1
    status = await scalar(
        engine_databases, "SELECT status FROM monitoring.job_runs WHERE job = 'run-weekly' ORDER BY id DESC LIMIT 1"
    )
    assert status == "succeeded"


# --- the dead-man's switch (ADR-014) ---


@pytest.mark.guardrail("pipeline.overdue_after_minutes")
async def test_a_due_run_not_finished_within_the_hour_shows_as_overdue(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await fixture_learner(engine_databases, rules, "made")
    query = "SELECT overdue FROM monitoring.pipeline_overdue_at(:now)"
    late = sunday_evening(learner.timezone) + timedelta(minutes=rules.pipeline.overdue_after_minutes + 1)
    before = int(await scalar(engine_databases, query, now=late))
    assert before >= 1
    await run_weekly(services_for(engine_databases, rules, crew_of()), learner, sunday_evening(learner.timezone))
    assert int(await scalar(engine_databases, query, now=late)) == before - 1


def test_the_overdue_alert_uses_the_rule_files_day_hour_and_grace(rules: Rules) -> None:
    import yaml
    from juku_testkit.databases import repo_root

    path = repo_root() / "ops" / "grafana" / "provisioning" / "alerting" / "rules.yaml"
    groups = yaml.safe_load(path.read_text(encoding="utf-8"))["groups"]
    [rule] = [rule for group in groups for rule in group["rules"] if rule["uid"] == "juku-pipeline-overdue"]
    pipeline = rules.pipeline
    expected = (
        f"pipeline_overdue_at(now(), {pipeline.due_weekday}, {pipeline.due_hour}, {pipeline.overdue_after_minutes})"
    )
    assert expected in rule["data"][0]["model"]["rawSql"]


# --- request_replan (SM4): a Keiko run under a chain delegated from Shiori ---


async def test_a_queued_replan_runs_keiko_with_a_token_delegated_from_shiori(
    engine_databases: Databases, rules: Rules, juku_mcp_url: str, key: ed25519.Ed25519PrivateKey
) -> None:
    learner = await fixture_learner(engine_databases, rules, "joko")
    async with engine_databases.app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO learning.replan_requests (learner_id, local_day, sequence_in_day, actor_chain) "
                "VALUES (:l, '2026-11-05', 1, ARRAY['agent:shiori'])"
            ),
            {"l": learner.id},
        )

    def keiko(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if not any(isinstance(part, ToolReturnPart) for message in messages for part in getattr(message, "parts", [])):
            return ModelResponse(parts=[ToolCallPart(tool_name="get_progress", args={})])
        return faithful_keiko(messages, info)

    models = CrewModels(
        keiko=FunctionModel(keiko), nikki=FunctionModel(faithful_nikki), tadashi=FunctionModel(approving_tadashi)
    )
    services = services_for(engine_databases, rules, build_crew(models, keiko_toolset(juku_mcp_url)), key=key)
    [outcome] = await run_replans(services, sunday_evening(learner.timezone))
    assert outcome.status == "replanned"
    async with engine_databases.app.connect() as connection:
        chain, outcome_of_call = (
            await connection.execute(
                text(
                    "SELECT actor_chain, outcome FROM monitoring.tool_calls "
                    "WHERE learner_id = :l ORDER BY id DESC LIMIT 1"
                ),
                {"l": learner.id},
            )
        ).one()
    assert (list(chain), outcome_of_call) == (["shiori", "keiko"], "ok"), "Juku's server accepted the delegated chain"
    handled = await scalar(
        engine_databases,
        "SELECT handled_at IS NOT NULL FROM learning.replan_requests WHERE learner_id = :l",
        l=learner.id,
    )
    assert handled is True
    assert await reports_of(engine_databases, learner) == 0, "a replan changes the plan, not the week's report"


# --- AG4: the feedback job drafts, and never applies ---


@pytest.mark.guardrail("pipeline.feedback_min_occurrences")
async def test_the_feedback_job_drafts_from_recurring_issues_only_and_never_sees_quotes(
    engine_databases: Databases, rules: Rules
) -> None:
    """A quiet week of its own (March 2027), so other tests' reviews don't count; one learner per occurrence."""
    flagged = {
        "grade": "C",
        "issues": [{"quote": "kalimat rahasia pelajar", "reason": "Terlalu kaku.", "severity": "medium"}],
        "feedback": "",
    }

    def tadashi(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return structured(
            info, flagged if prompt_of(messages)["author"] == "nikki" else {"grade": "A", "issues": [], "feedback": ""}
        )

    services = services_for(engine_databases, rules, crew_of(tadashi=tadashi))
    for name in ["joko", "oka", "made"][: rules.pipeline.feedback_min_occurrences]:
        learner = await fixture_learner(engine_databases, rules, name)
        await run_weekly(services, learner, sunday_evening(learner.timezone, on="2027-03-07"))
    seen: list[str] = []

    def drafter(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        seen.append(json.dumps(prompt_of(messages), ensure_ascii=False))
        return ModelResponse(parts=[TextPart("Saran: minta Nikki menulis lebih hangat.")])

    drafts = await draft_feedback(
        engine_databases.app, FunctionModel(drafter), rules, sunday_evening("Asia/Jakarta", on="2027-03-08")
    )
    assert [(draft.agent, draft.status) for draft in drafts] == [("nikki", "draft")]
    assert "Terlalu kaku." in seen[0]
    assert "kalimat rahasia pelajar" not in seen[0], "quotes are learner content; the job sees reasons and counts only"


# --- AG3: the Run Inspector (Arthur only) and the learner's report page ---


async def test_the_run_inspector_is_for_arthur_only(engine_databases: Databases, rules: Rules) -> None:
    learner = await fixture_learner(engine_databases, rules)
    outcome = await run_weekly(
        services_for(engine_databases, rules, crew_of()), learner, sunday_evening(learner.timezone)
    )
    arthur_code, other_code = await issue_codes(engine_databases.app, 2)
    async with client_for(deps(engine_databases)) as other:
        await sign_up(other, other_code, nickname="Bukan")
        assert (await other.get("/admin/runs")).status_code == 404
    async with client_for(deps(engine_databases)) as first_visit:
        await sign_up(first_visit, arthur_code, nickname="Arthur")
    arthur_id = str(await scalar(engine_databases, "SELECT public_id FROM learning.learners WHERE nickname = 'Arthur'"))
    async with client_for(deps(engine_databases, admin_public_ids=frozenset({arthur_id}))) as arthur:
        page = await arthur.get("/masuk")
        await arthur.post("/masuk", data={"code": arthur_code, "csrf": csrf_of(page)})
        runs = await arthur.get("/admin/runs")
        detail = await arthur.get(f"/admin/runs/{outcome.run_id}")
    assert runs.status_code == 200 and f"/admin/runs/{outcome.run_id}" in runs.text
    assert detail.status_code == 200
    for part in ("keiko", "nikki", "grade A", "published"):
        assert part in detail.text


async def test_a_learner_reads_their_latest_report(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Pembaca")
        learner_id = int(await scalar(engine_databases, "SELECT id FROM learning.learners WHERE nickname = 'Pembaca'"))
        async with engine_databases.app.begin() as connection:
            run_id = await connection.scalar(
                text(
                    "INSERT INTO app.pipeline_runs (learner_id, week_start, kind, status, started_at) "
                    "VALUES (:l, '2026-11-02', 'weekly', 'published', now()) RETURNING id"
                ),
                {"l": learner_id},
            )
            await connection.execute(
                text(
                    "INSERT INTO app.reports (learner_id, run_id, week_start, body, is_fallback, created_at, "
                    "expires_at) VALUES (:l, :r, '2026-11-02', 'Laporan minggu ini [ref:activity].', false, now(), "
                    "now() + interval '90 days')"
                ),
                {"l": learner_id, "r": run_id},
            )
        page = await client.get("/laporan")
    assert page.status_code == 200
    assert "Laporan minggu ini" in page.text
