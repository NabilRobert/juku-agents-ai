"""When the weekly run happens: Sunday 18:00 in each learner's timezone (AG2), and the dead-man's switch."""

from datetime import timedelta

import pytest
from juku_app.pipeline.run import due_learners, run_due, run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from pipeline_helpers import (
    crew_of,
    fixture_learner,
    reports_of,
    scalar,
    services_for,
    sunday_evening,
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
