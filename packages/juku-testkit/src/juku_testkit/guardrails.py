"""G1's harness: every rule in guardrails.yaml has a test (ADR-019; Phase 1, G1).

A guardrail test is marked with the rule it enforces, by its path in the
rule file:

    @pytest.mark.guardrail("delegation.max_agent_hops")
    def test_a_chain_three_agents_deep_is_refused(): ...

The rules are found from the rule file's own model, so a rule added to
guardrails.yaml is a rule that needs a test. With `--guardrails-complete`
(make check sets it), a rule with no test fails the run, and the summary
lists each rule's test count.
"""

from __future__ import annotations

from collections import Counter

import pytest
from juku_common.rules import Rules, Section, load_rules

MARKER = "guardrail"
# The rule file's sections that are guardrails. `fitness` has its own harness (fitness.py).
GUARDRAIL_SECTIONS = ("alerts", "privacy", "delegation", "agents", "replan", "budget", "memory", "database")


def rule_paths(rules: Rules) -> list[str]:
    """`section.rule` for every rule in the guardrail sections; a section that's a plain mapping is one rule."""
    paths: list[str] = []
    for section_name in GUARDRAIL_SECTIONS:
        section = getattr(rules, section_name)
        if isinstance(section, Section):
            paths += [f"{section_name}.{field}" for field in type(section).model_fields]
        else:
            paths.append(section_name)
    return paths


class GuardrailHarness:
    def __init__(self, rules: Rules, *, require_complete: bool) -> None:
        self.paths = rule_paths(rules)
        self.require_complete = require_complete
        self.collected: Counter[str] = Counter()

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        for item in items:
            for marker in item.iter_markers(MARKER):
                path = str(marker.args[0])
                if path not in self.paths:
                    raise pytest.UsageError(
                        f"{item.nodeid} is marked {MARKER}({path!r}), not a rule in guardrails.yaml"
                    )
                self.collected[path] += 1

    def missing(self) -> list[str]:
        return [path for path in self.paths if self.collected[path] == 0]

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        terminalreporter.section("guardrails with tests (G1)")
        tested = len(self.paths) - len(self.missing())
        terminalreporter.write_line(f"{tested} of {len(self.paths)} rules in guardrails.yaml have a test")
        for path in self.missing():
            terminalreporter.write_line(f"  no test: {path}", red=self.require_complete)

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if self.require_complete and self.missing():
            session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--guardrails-complete",
        action="store_true",
        help="fail if a rule in guardrails.yaml has no test marked with it (make check sets this)",
    )


def pytest_configure(config: pytest.Config) -> None:
    example = f'{MARKER}("replan.max_requests_per_day")'
    config.addinivalue_line("markers", f"{MARKER}(path): this test enforces a rule in guardrails.yaml, e.g. {example}")
    harness = GuardrailHarness(load_rules(), require_complete=bool(config.getoption("--guardrails-complete")))
    config.pluginmanager.register(harness, "juku-guardrail-harness")
