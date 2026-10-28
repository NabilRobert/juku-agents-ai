"""The agents' typed outputs (juku_app.pipeline.outputs): Pitstop's rule that a missing severity is high."""

from juku_app.pipeline.outputs import Issue


def test_an_issue_without_a_severity_counts_as_high() -> None:
    assert Issue(reason="x").severity == "high"
