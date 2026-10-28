"""Stub until the pipeline lands (EDD1): code's own high-severity checks on Keiko's plan and Nikki's report."""

from __future__ import annotations

from juku_common.rules import Rules

from juku_app.pipeline.facts import WeekFacts
from juku_app.pipeline.outputs import Issue, KeikoPlan


def check_plan(plan: KeikoPlan, facts: WeekFacts, fresh: WeekFacts, rules: Rules) -> list[Issue]:
    raise NotImplementedError


def check_report(report: str, plan: KeikoPlan, facts: WeekFacts, fresh: WeekFacts, rules: Rules) -> list[Issue]:
    raise NotImplementedError
