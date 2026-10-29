"""The rule file loader: a bad guardrails.yaml stops start-up with a clear message."""

from pathlib import Path

import pytest
from juku_common.rules import RulesError, load_rules

VALID = """
version: 1
alerts:
  heartbeat_stale_seconds: 300
  tool_error_rate_per_hour: 0.05
privacy:
  min_learners_per_cell: 5
delegation:
  issuer: juku-app
  audience: juku-mcp
  token_ttl_seconds: 60
  max_agent_hops: 2
  require_gateway_caller: true
  allowed_delegations:
    - {from_agent: shiori, to_agent: keiko, via_tool: request_replan}
agents:
  shiori: [get_progress, request_replan]
  keiko: [get_progress]
replan:
  max_requests_per_day: 1
budget:
  input_usd_per_million: 0.25
  output_usd_per_million: 2.00
  reports_pool_usd: 0.90
  chat_pool_usd: 1.20
  chat_daily_global_usd: 0.20
  chat_daily_questions_per_learner: 20
  chat_run_request_limit: 6
  chat_run_total_tokens_limit: 20000
  report_run_request_limit: 8
  report_run_total_tokens_limit: 40000
  alert_fractions: [0.5, 0.8, 1.0]
memory:
  allowed_categories: [recurring_confusion, pace]
  forbidden_categories: [health]
  forbidden_text_markers: [sakit]
  min_evidence_events: 3
  evidence_max_age_days: 30
  contradicting_answers: 2
  suppress_after_removal_days: 30
  max_active_notes: 12
  max_text_chars: 160
pipeline:
  max_revisions: 2
  report_max_words: 300
  due_weekday: 6
  due_hour: 18
  run_lease_minutes: 30
  overdue_after_minutes: 60
  feedback_min_occurrences: 3

database:
  connection_limit: 20
  reserved_for_admin: 2
  app_pool: 3
  app_dict_pool: 2
  app_commands: 1
  mcp_pool: 3
  mcp_dict_pool: 2
  ops_connections: 2
  migrator_connections: 1
  dict_owner_connections: 1
  grafana_connections: 2
  mcp_backbone_connections: 1
fitness:
  FF4:
    title: Migrations are safe
    status: active
    checked_by: squawk
  FF1:
    title: Query plans
    status: pending
    until: track A
    thresholds:
      recommend_words_max_ms: 200
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "guardrails.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_the_committed_rule_file_is_valid() -> None:
    rules = load_rules()
    assert rules.version == 1
    assert "FF4" in rules.fitness


def test_a_threshold_is_read_by_name(tmp_path: Path) -> None:
    rules = load_rules(write(tmp_path, VALID))
    assert rules.threshold("FF1", "recommend_words_max_ms") == 200


def test_a_missing_threshold_names_the_key_to_add(tmp_path: Path) -> None:
    rules = load_rules(write(tmp_path, VALID))
    with pytest.raises(RulesError, match="FF1 has no threshold 'plan_cost'"):
        rules.threshold("FF1", "plan_cost")


def test_an_unknown_fitness_function_is_an_error(tmp_path: Path) -> None:
    rules = load_rules(write(tmp_path, VALID))
    with pytest.raises(RulesError, match=r"FF99 isn't in guardrails\.yaml"):
        rules.fitness_function("FF99")


def test_an_unknown_key_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match=r"fitness\.FF4\.treshold"):
        load_rules(write(tmp_path, VALID.replace("checked_by: squawk", "checked_by: squawk\n    treshold: 3")))


def test_a_pending_fitness_function_must_name_its_slice(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match="needs `until`"):
        load_rules(write(tmp_path, VALID.replace("    until: track A\n", "")))


def test_an_active_fitness_function_cannot_be_waiting_for_a_slice(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match="can't have `until`"):
        load_rules(write(tmp_path, VALID.replace("status: active", "status: active\n    until: later")))


def test_an_unsupported_version_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match="version 2 isn't supported"):
        load_rules(write(tmp_path, VALID.replace("version: 1", "version: 2")))


def test_a_missing_file_says_where_it_looked(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match="can't read the rule file"):
        load_rules(tmp_path / "nope.yaml")


def test_the_path_can_come_from_the_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUKU_RULES_PATH", str(write(tmp_path, VALID)))
    assert set(load_rules().fitness) == {"FF4", "FF1"}


def test_an_alert_threshold_out_of_range_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RulesError, match=r"alerts\.tool_error_rate_per_hour"):
        load_rules(write(tmp_path, VALID.replace("tool_error_rate_per_hour: 0.05", "tool_error_rate_per_hour: 5")))


@pytest.mark.guardrail("delegation.allowed_delegations")
def test_a_delegation_that_would_widen_the_tools_is_refused_at_load(tmp_path: Path) -> None:
    widened = VALID.replace("keiko: [get_progress]", "keiko: [get_progress, get_memory]")
    with pytest.raises(RulesError, match="keiko would get tools shiori lacks"):
        load_rules(write(tmp_path, widened))


@pytest.mark.guardrail("delegation.allowed_delegations")
def test_a_delegation_through_a_tool_the_agent_lacks_is_refused_at_load(tmp_path: Path) -> None:
    lacking = VALID.replace("shiori: [get_progress, request_replan]", "shiori: [get_progress]")
    with pytest.raises(RulesError, match="can't delegate through request_replan"):
        load_rules(write(tmp_path, lacking))


def test_an_unknown_agent_has_no_tools(tmp_path: Path) -> None:
    assert load_rules(write(tmp_path, VALID)).tools_of("mallory") == frozenset()
