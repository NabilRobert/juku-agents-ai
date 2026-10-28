"""Approval, decided in code (ADR-007): Pitstop's rule, plus code's own checks.

Ported from Pitstop's critic (gads-case-study e15697e,
backend/src/agents/critic.ts: decideApproval): no review, no grade, or a D
or F blocks; any high-severity issue blocks; medium and low issues approve
with notes. Juku adds code's issues (juku_app.pipeline.checks), which block
whatever Tadashi says.
"""

from __future__ import annotations

from dataclasses import dataclass

from juku_app.pipeline.outputs import Issue, Review

FAILING_GRADES = ("D", "F")


@dataclass(frozen=True)
class Decision:
    is_approved: bool
    reason: str


def decide_approval(review: Review | None, code_issues: list[Issue]) -> Decision:
    code_high = sorted({str(issue.kind) for issue in code_issues if issue.severity == "high"})
    if code_high:
        return Decision(False, "code: " + ", ".join(code_high))
    if review is None:
        return Decision(False, "review unavailable")
    if review.grade is None:
        return Decision(False, "no valid grade")
    if review.grade in FAILING_GRADES:
        return Decision(False, f"grade {review.grade}")
    high = sum(1 for issue in review.issues if issue.severity == "high")
    if high:
        return Decision(False, f"{high} high-severity issue{'s' if high > 1 else ''}")
    medium = sum(1 for issue in review.issues if issue.severity == "medium")
    low = sum(1 for issue in review.issues if issue.severity == "low")
    notes = ", ".join(part for part in (f"{medium} medium" if medium else "", f"{low} low" if low else "") if part)
    return Decision(True, f"grade {review.grade}, approved with notes ({notes})" if notes else f"grade {review.grade}")
