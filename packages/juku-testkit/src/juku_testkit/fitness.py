"""The fitness-function harness: a pytest plugin (scale path, ADR-023).

A fitness function is a test marked with the ID it enforces:

    @pytest.mark.fitness("FF3")
    def test_incremental_state_matches_a_full_recompute(): ...

Its thresholds come from guardrails.yaml through the `rules` fixture, never
from constants in the test, so raising one is a reviewed change to that file.

At the end of every run the harness prints one line per fitness function:
how many of its tests passed, failed or were skipped, or which slice it is
waiting for. `make check` adds `--fitness-complete`, which fails the run if
an active fitness function checked by pytest has no test at all. That stops
one being dropped by deleting its tests.
"""

from __future__ import annotations

from collections import Counter

import pytest
from juku_common.rules import Rules, load_rules

MARKER = "fitness"
_RULES = pytest.StashKey[Rules]()


def fitness_ids(item: pytest.Item) -> list[str]:
    """The fitness functions a test is marked with."""
    return [str(marker.args[0]) for marker in item.iter_markers(MARKER) if marker.args]


class FitnessHarness:
    """Counts each fitness function's tests and outcomes for one pytest run."""

    def __init__(self, rules: Rules, *, require_complete: bool) -> None:
        self.rules = rules
        self.require_complete = require_complete
        self.collected: Counter[str] = Counter()
        self.outcomes: dict[str, Counter[str]] = {}
        self.ids_by_test: dict[str, list[str]] = {}

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        for item in items:
            ids = fitness_ids(item)
            for ff_id in ids:
                if ff_id not in self.rules.fitness:
                    raise pytest.UsageError(f"{item.nodeid} is marked {MARKER}({ff_id!r}), not in guardrails.yaml")
                self.collected[ff_id] += 1
            if ids:
                self.ids_by_test[item.nodeid] = ids

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # A test's outcome is its call phase, or its setup if setup didn't pass (a skip or an error).
        is_final_phase = report.when == "call" or (report.when == "setup" and not report.passed)
        if not is_final_phase:
            return
        for ff_id in self.ids_by_test.get(report.nodeid, []):
            self.outcomes.setdefault(ff_id, Counter())[report.outcome] += 1

    def missing_active(self) -> list[str]:
        """Active fitness functions, checked by pytest, with no test collected."""
        return [
            ff_id
            for ff_id, ff in self.rules.fitness.items()
            if ff.status == "active" and ff.checked_by == "pytest" and self.collected[ff_id] == 0
        ]

    def state_of(self, ff_id: str) -> str:
        ff = self.rules.fitness[ff_id]
        if ff.status == "pending":
            return f"pending until {ff.until}"
        if ff.checked_by != "pytest":
            return f"checked by {ff.checked_by} (make check)"
        if self.collected[ff_id] == 0:
            return "ACTIVE BUT NO TEST"
        outcomes = self.outcomes.get(ff_id, Counter[str]())
        return ", ".join(f"{count} {outcome}" for outcome, count in sorted(outcomes.items())) or "not run"

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        terminalreporter.section("fitness functions (guardrails.yaml)")
        for ff_id, ff in self.rules.fitness.items():
            terminalreporter.write_line(f"{ff_id:<5} {ff.title}: {self.state_of(ff_id)}")
        missing = self.missing_active()
        if self.require_complete and missing:
            terminalreporter.write_line(
                f"Active in guardrails.yaml but with no test: {', '.join(missing)}. "
                "Add a test marked @pytest.mark.fitness(...), or set the entry back to pending.",
                red=True,
            )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.require_complete and self.missing_active():
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--fitness-complete",
        action="store_true",
        help="fail if an active fitness function in guardrails.yaml has no test (make check sets this)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", f'{MARKER}(id): this test enforces a fitness function, e.g. {MARKER}("FF3")')
    rules = load_rules()
    config.stash[_RULES] = rules
    harness = FitnessHarness(rules, require_complete=bool(config.getoption("--fitness-complete")))
    config.pluginmanager.register(harness, "juku-fitness-harness")


@pytest.fixture(scope="session")
def rules(pytestconfig: pytest.Config) -> Rules:
    """The rule file, as loaded for this run."""
    return pytestconfig.stash[_RULES]
