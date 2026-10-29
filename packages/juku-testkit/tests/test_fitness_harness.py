"""The fitness-function harness: an active fitness function can't lose its tests unnoticed."""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

RULES = """
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
  FF3:
    title: Incremental state equals a full recompute
    status: active
  FF4:
    title: Migrations are safe
    status: active
    checked_by: squawk
  FF7:
    title: Idempotent runs
    status: pending
    until: slice 6
"""


@pytest.fixture
def rules_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "guardrails.yaml"
    path.write_text(RULES, encoding="utf-8")
    monkeypatch.setenv("JUKU_RULES_PATH", str(path))
    return path


@pytest.mark.usefixtures("rules_file")
def test_an_active_fitness_function_with_a_test_passes_the_complete_check(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.fitness("FF3")
        def test_recompute():
            assert True
        """
    )
    result = pytester.runpytest("--fitness-complete", "-p", "no:cacheprovider", "-p", "no:asyncio")
    result.assert_outcomes(passed=1)
    result.stdout.fnmatch_lines(["FF3 * 1 passed", "FF4 * checked by squawk*", "FF7 * pending until slice 6"])


@pytest.mark.usefixtures("rules_file")
def test_an_active_fitness_function_without_a_test_fails_the_complete_check(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_unrelated():\n    assert True\n")
    result = pytester.runpytest("--fitness-complete", "-p", "no:cacheprovider", "-p", "no:asyncio")
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result.stdout.fnmatch_lines(["FF3 * ACTIVE BUT NO TEST", "*with no test: FF3*"])


@pytest.mark.usefixtures("rules_file")
def test_without_the_complete_flag_a_missing_test_is_only_reported(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("def test_unrelated():\n    assert True\n")
    result = pytester.runpytest("-p", "no:cacheprovider", "-p", "no:asyncio")
    assert result.ret == pytest.ExitCode.OK


@pytest.mark.usefixtures("rules_file")
def test_a_marker_naming_an_unknown_fitness_function_is_a_usage_error(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.fitness("FF99")
        def test_typo():
            assert True
        """
    )
    result = pytester.runpytest("-p", "no:cacheprovider", "-p", "no:asyncio")
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    result.stderr.fnmatch_lines(["*FF99*not in guardrails.yaml*"])


@pytest.mark.usefixtures("rules_file")
def test_a_failing_fitness_test_is_counted_against_its_function(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.fitness("FF3")
        def test_recompute():
            assert False
        """
    )
    result = pytester.runpytest("-p", "no:cacheprovider", "-p", "no:asyncio")
    result.stdout.fnmatch_lines(["FF3 * 1 failed"])
