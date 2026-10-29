"""Grafana's provisioned files (ADR-009, Phase 2 M4-M5): safe to screenshot, and every query runs.

Each dashboard and alert query is run against the migrated test database
as `grafana_reader`, so a broken query fails here, not on the server.
"""

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from juku_common.rules import Rules
from juku_testkit.databases import repo_root
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

GRAFANA = repo_root() / "ops" / "grafana"
DATASOURCE_UID = "juku-monitoring"
EXPRESSION_UID = "__expr__"
# M4: no panel shows a nickname, question text or one learner's data.
FORBIDDEN = re.compile(r"\b(learner_id|learners|nickname|question|answer|chat_messages|reports?_text|memory_notes)\b")
TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_]+)\.([a-z_]+)", re.IGNORECASE)
M5_ALERTS = {
    "juku-heartbeat-stale",
    "juku-missed-run",
    "juku-tool-error-rate",
    "juku-detector-flag",
    "juku-audit-chain-broken",
    "juku-mcp-refusal",
    # Beyond M5: the daily checks' "scheduled runs completed" (standard checks, section 6).
    "juku-job-failed",
}


def load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def alert_rules() -> list[dict[str, Any]]:
    document = load_yaml(GRAFANA / "provisioning" / "alerting" / "rules.yaml")
    return [rule for group in document["groups"] for rule in group["rules"]]


def dashboard_queries() -> list[tuple[str, dict[str, Any]]]:
    queries: list[tuple[str, dict[str, Any]]] = []
    for path in sorted((GRAFANA / "dashboards").glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        for panel in dashboard["panels"]:
            for target in panel["targets"]:
                queries.append((f"{path.name}: {panel['title']}", target))
    return queries


def all_sql() -> list[tuple[str, str]]:
    found = [(where, str(target["rawSql"])) for where, target in dashboard_queries()]
    for rule in alert_rules():
        for step in rule["data"]:
            if step["datasourceUid"] == DATASOURCE_UID:
                found.append((f"alert {rule['uid']}", str(step["model"]["rawSql"])))
    return found


def test_every_dashboard_query_uses_the_read_only_data_source() -> None:
    assert dashboard_queries(), "no dashboard found"
    for where, target in dashboard_queries():
        assert target["datasource"]["uid"] == DATASOURCE_UID, where


def test_every_alert_step_uses_the_read_only_data_source_or_an_expression() -> None:
    for rule in alert_rules():
        assert {step["datasourceUid"] for step in rule["data"]} <= {DATASOURCE_UID, EXPRESSION_UID}, rule["uid"]


@pytest.mark.parametrize(("where", "sql"), all_sql())
def test_no_query_reads_learner_data_or_content(where: str, sql: str) -> None:
    assert not FORBIDDEN.search(sql), f"{where} mentions {FORBIDDEN.search(sql)}"
    schemas = {schema for schema, _ in TABLE_REFERENCE.findall(sql)}
    assert schemas <= {"monitoring"}, f"{where} reads {schemas}"


def test_every_m5_alert_is_provisioned() -> None:
    assert {rule["uid"] for rule in alert_rules()} >= M5_ALERTS


def threshold_of(uid: str) -> float:
    rule = next(rule for rule in alert_rules() if rule["uid"] == uid)
    condition = next(step for step in rule["data"] if step["refId"] == rule["condition"])
    return float(condition["model"]["conditions"][0]["evaluator"]["params"][0])


@pytest.mark.guardrail("alerts.heartbeat_stale_seconds")
@pytest.mark.guardrail("alerts.tool_error_rate_per_hour")
def test_alert_thresholds_match_the_rule_file(rules: Rules) -> None:
    assert threshold_of("juku-heartbeat-stale") == rules.alerts.heartbeat_stale_seconds
    assert threshold_of("juku-tool-error-rate") == rules.alerts.tool_error_rate_per_hour


def test_an_empty_table_counts_as_alerting_not_as_quiet() -> None:
    assert {rule["noDataState"] for rule in alert_rules()} == {"Alerting"}


def test_the_telegram_token_comes_from_a_secret_file() -> None:
    document = load_yaml(GRAFANA / "provisioning" / "alerting" / "contact-points.yaml")
    settings = document["contactPoints"][0]["receivers"][0]["settings"]
    assert settings["bottoken"] == "$__file{/run/secrets/telegram_bot_token}"
    assert settings["chatid"] == "$JUKU_TELEGRAM_CHAT_ID"


def test_the_data_source_password_comes_from_a_secret_file() -> None:
    document = load_yaml(GRAFANA / "provisioning" / "datasources" / "monitoring.yaml")
    datasource = document["datasources"][0]
    assert datasource["user"] == "grafana_reader"
    assert datasource["secureJsonData"]["password"].startswith("$__file{/run/secrets/")


def as_plain_sql(sql: str) -> str:
    """Grafana's macros, replaced with what they expand to for a 7-day range."""
    return re.sub(r"\$__timeFilter\((\w+)\)", r"\1 > now() - interval '7 days'", sql)


@pytest.mark.parametrize(("where", "sql"), all_sql())
async def test_every_query_runs_as_grafana_reader(app_engine: AsyncEngine, where: str, sql: str) -> None:
    async with app_engine.connect() as connection:
        await connection.execute(text("SET ROLE grafana_reader"))
        result = await connection.execute(text(as_plain_sql(sql)))
        assert result.keys(), where
        await connection.rollback()
