"""`juku-ops`: a job with nothing to do, or a problem, exits 1 with a message saying why."""

import pytest
from juku_ops.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_import_audit_without_any_log_configured_says_which_settings_to_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JUKU_OPS_DATABASE_URL", "postgresql+asyncpg://unused/app")
    monkeypatch.delenv("JUKU_GATEWAY_AUDIT_LOG", raising=False)
    monkeypatch.delenv("JUKU_JUKU_MCP_AUDIT_LOG", raising=False)
    result = runner.invoke(app, ["import-audit"])
    assert result.exit_code == 1
    assert "JUKU_GATEWAY_AUDIT_LOG" in result.output


def test_ensure_partitions_without_the_owner_url_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUKU_OPS_DATABASE_URL", "postgresql+asyncpg://unused/app")
    monkeypatch.delenv("JUKU_MIGRATOR_DATABASE_URL", raising=False)
    result = runner.invoke(app, ["ensure-partitions"])
    assert result.exit_code == 1
    assert "JUKU_MIGRATOR_DATABASE_URL" in result.output


def test_heartbeat_does_not_beat_when_the_app_does_not_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUKU_OPS_DATABASE_URL", "postgresql+asyncpg://unused/app")
    monkeypatch.setenv("JUKU_APP_HEALTH_URL", "http://127.0.0.1:9/healthz")
    result = runner.invoke(app, ["heartbeat"])
    assert result.exit_code == 1
    assert "didn't answer 200" in result.output


def test_consolidate_memory_without_the_app_url_says_why(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUKU_OPS_DATABASE_URL", "postgresql+asyncpg://unused/app")
    monkeypatch.delenv("JUKU_APP_DATABASE_URL", raising=False)
    result = runner.invoke(app, ["consolidate-memory"])
    assert result.exit_code == 1
    assert "JUKU_APP_DATABASE_URL" in result.output
