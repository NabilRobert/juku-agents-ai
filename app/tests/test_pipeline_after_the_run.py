"""Around the weekly run: replans queued by Shiori, the feedback job, the Run Inspector and the report page."""

import json

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app import owner
from juku_app.invites import issue_codes
from juku_app.pipeline.crew import CrewModels, build_crew, keiko_toolset
from juku_app.pipeline.feedback import draft_feedback
from juku_app.pipeline.run import run_replans, run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from pipeline_helpers import (
    approving_tadashi,
    crew_of,
    faithful_keiko,
    faithful_nikki,
    fixture_learner,
    prompt_of,
    reports_of,
    scalar,
    services_for,
    structured,
    sunday_evening,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import text
from web_helpers import client_for, csrf_of, deps, page_props, sign_up

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
    await owner.set_role(engine_databases.app, owner.COMMAND_LINE, arthur_id, "owner")
    async with client_for(deps(engine_databases)) as arthur:
        page = await arthur.get("/masuk")
        await arthur.post("/masuk", data={"code": arthur_code, "csrf": csrf_of(page)})
        runs = await arthur.get("/admin/runs")
        detail = await arthur.get(f"/admin/runs/{outcome.run_id}")
    assert runs.status_code == 200 and outcome.run_id in [run["id"] for run in page_props(runs)["runs"]]
    assert detail.status_code == 200
    shown = page_props(detail)
    assert shown["run"]["status"] == "published"
    assert {attempt["agent"] for attempt in shown["attempts"]} == {"keiko", "nikki"}
    assert "A" in {attempt["grade"] for attempt in shown["attempts"]}


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
