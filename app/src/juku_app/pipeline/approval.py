"""Stub until the pipeline lands (EDD1): approval decided in code, from Tadashi's review and code's own checks."""

from __future__ import annotations

from dataclasses import dataclass

from juku_app.pipeline.outputs import Issue, Review


@dataclass(frozen=True)
class Decision:
    is_approved: bool
    reason: str


def decide_approval(review: Review | None, code_issues: list[Issue]) -> Decision:
    raise NotImplementedError
