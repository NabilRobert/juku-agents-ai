"""Stub until the pipeline lands (EDD1): the facts-only report, from a template, when an output can't pass."""

from __future__ import annotations

from juku_app.pipeline.facts import WeekFacts


def facts_only_report(facts: WeekFacts) -> str:
    raise NotImplementedError
