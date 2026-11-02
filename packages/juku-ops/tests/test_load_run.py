"""The load test's runner survives a failed Locust step, and its sampler can't outlive the run."""

import importlib.util
import json
import subprocess
import threading
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RUN_PY = Path(__file__).resolve().parents[3] / "evals" / "load" / "run.py"


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("load_run", RUN_PY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "BUILD", tmp_path)
    monkeypatch.setattr(module, "restart_count", lambda: {})
    return module


def test_a_failed_locust_step_is_recorded_instead_of_ending_the_run(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    def locust_with_a_failed_request(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert kwargs["check"] is False
        groups = {"times_ms": {"chat": [10.0, 20.0, 30.0]}, "failures": {"chat": 1}}
        Path(kwargs["env"]["JUKU_LOAD_OUT"]).write_text(json.dumps(groups))
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(runner, "sh", locust_with_a_failed_request)
    step = runner.run_step(users=1, seconds=1)
    assert step["locust_exit"] == 1
    assert step["groups"]["chat"]["failures"] == 1


def test_the_sampler_stops_when_locust_cannot_start(runner: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def locust_that_cannot_start(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    threads_before = threading.active_count()
    monkeypatch.setattr(runner, "sh", locust_that_cannot_start)
    with pytest.raises(FileNotFoundError):
        runner.run_step(users=1, seconds=1)
    assert threading.active_count() == threads_before
