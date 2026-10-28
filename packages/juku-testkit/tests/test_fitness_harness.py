"""The fitness-function harness: an active fitness function can't lose its tests unnoticed."""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

RULES = """
version: 1
alerts:
  heartbeat_stale_seconds: 300
  tool_error_rate_per_hour: 0.05
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
