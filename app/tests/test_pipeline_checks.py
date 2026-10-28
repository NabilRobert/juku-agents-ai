"""Code's own high-severity checks (ADR-007), and approval decided in code (ported from Pitstop's critic)."""

from datetime import UTC, date, datetime

import pytest
from juku_app.pipeline.approval import decide_approval
from juku_app.pipeline.checks import check_plan, check_report
from juku_app.pipeline.facts import WeekActivity, WeekFacts
from juku_app.pipeline.outputs import Issue, KeikoPlan, PlanWord, Review
from juku_common.rules import Rules
from juku_data.engine.models import (
    DayActivity,
    LevelCoverage,
    MistakeItem,
    Mistakes,
    Plan,
    Progress,
    Recommendations,
    RecommendedWord,
)
from juku_data.memory import EvidenceEvent, Memory, MemoryNote, NoteProposal

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the pipeline lands in the next commit")


def candidate(word_id: str, level: int = 5) -> RecommendedWord:
    return RecommendedWord(
        word_id=word_id,
        word="一つ",
        reading="ひとつ",
        level=level,
        meanings=["one"],
        new_kanji=None,
        leverage=3,
        reason="x",
    )


def note(note_id: str) -> MemoryNote:
    evidence = EvidenceEvent(
        event_id=1,
        event_type="quiz_reading",
        word_id="w9",
        word="読む",
        reading="よむ",
        level=5,
        is_correct=False,
        occurred_on=date(2026, 11, 2),
    )
    return MemoryNote(
        note_id=note_id,
        category="recurring_confusion",
        text="Sering salah membaca 読む.",
        evidence=[evidence],
        noted_on=date(2026, 11, 3),
        last_evidence_on=date(2026, 11, 2),
        age_days=5,
    )


def sample_facts(*, notes: tuple[str, ...] = ("note-1",), mistakes: tuple[str, ...] = ("m1",)) -> WeekFacts:
    """A week: 12 quiz answers, 9 right, 40 words known, two candidates at N5 and N4."""
    return WeekFacts(
        week_start=date(2026, 11, 2),
        week_end=date(2026, 11, 8),
        target_level=5,
        progress=Progress(
            target_level=5,
            known_words=40,
            levels=[
                LevelCoverage(
                    level=5,
                    level_name="N5",
                    words_known=40,
                    words_total=674,
                    kanji_known=6,
                    kanji_total=84,
                    word_coverage=40 / 674,
                    kanji_coverage=6 / 84,
                )
            ],
        ),
        activity=WeekActivity(
            quiz_answers=12,
            quiz_correct=9,
            words_marked=3,
            sentences_read=1,
            days=[
                DayActivity(day=date(2026, 11, 3), quiz_answers=12, quiz_correct=9, words_marked=3, sentences_read=1)
            ],
        ),
        mistakes=Mistakes(
            items=[
                MistakeItem(
                    word_id=word_id,
                    word="猫",
                    reading="ねこ",
                    box=1,
                    due_at=datetime(2026, 11, 6, tzinfo=UTC),
                    is_due=True,
                )
                for word_id in mistakes
            ]
        ),
        candidates=Recommendations(words=[candidate("c5", 5), candidate("c4", 4)]),
        plan=Plan(
            target_level=5,
            target_coverage=0.8,
            words_in_scope=674,
            words_known=40,
            words_needed=499,
            exam_date=None,
            weeks_left=None,
            words_per_week=None,
            formula="-",
        ),
        memory=Memory(notes=[note(note_id) for note_id in notes], note="-"),
    )


def plan(**overrides: object) -> KeikoPlan:
    values: dict[str, object] = {
        "focus": [PlanWord(word_id="c5", level=5, reason="Kata baru.")],
        "review_word_ids": ["m1"],
        "explanation": "Minggu ini kamu menjawab 12 kuis [ref:activity].",
        "note_proposals": [],
    }
    return KeikoPlan.model_validate({**values, **overrides})


def kinds(issues: list[Issue]) -> set[str]:
    assert all(issue.source == "code" and issue.severity == "high" for issue in issues)
    return {str(issue.kind) for issue in issues}


GOOD_REPORT = "Minggu ini kamu menjawab 12 kuis dan 9 benar [ref:activity]. Kamu menguasai 40 kata [ref:progress]."


# --- Keiko's plan ---


def test_a_plan_from_the_candidates_and_the_mistakes_queue_passes(rules: Rules) -> None:
    facts = sample_facts()
    assert check_plan(plan(), facts, facts, rules) == []


def test_a_word_outside_the_candidates_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    bad = plan(focus=[PlanWord(word_id="elsewhere", level=5, reason="x")])
    assert kinds(check_plan(bad, facts, facts, rules)) == {"word_not_a_candidate"}


def test_a_candidate_at_the_wrong_level_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    bad = plan(focus=[PlanWord(word_id="c4", level=5, reason="x")])
    assert kinds(check_plan(bad, facts, facts, rules)) == {"off_level_word"}


def test_a_review_word_outside_the_mistakes_queue_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    assert kinds(check_plan(plan(review_word_ids=["c5"]), facts, facts, rules)) == {"word_not_in_mistakes"}


@pytest.mark.guardrail("memory.forbidden_categories")
def test_a_plan_proposing_a_forbidden_note_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    bad = plan(note_proposals=[NoteProposal(category="health", text="Sering lelah.", evidence_event_ids=[1])])
    assert kinds(check_plan(bad, facts, facts, rules)) == {"forbidden_note"}


def test_a_plans_explanation_is_held_to_the_facts_too(rules: Rules) -> None:
    facts = sample_facts()
    assert kinds(check_plan(plan(explanation="Kamu menjawab 13 kuis [ref:activity]."), facts, facts, rules)) == {
        "number_not_in_facts"
    }


# --- Nikki's report ---


def test_a_report_of_cited_facts_passes(rules: Rules) -> None:
    facts = sample_facts()
    assert check_report(GOOD_REPORT, plan(), facts, facts, rules) == []


def test_a_number_not_in_the_facts_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    report = "Minggu ini kamu menjawab 13 kuis [ref:activity]."
    assert kinds(check_report(report, plan(), facts, facts, rules)) == {"number_not_in_facts"}


def test_the_weeks_dates_and_word_levels_are_not_counted_as_claims(rules: Rules) -> None:
    facts = sample_facts()
    report = "Laporan 2026-11-02 sampai 2026-11-08: 12 kuis [ref:activity], kata N5 [ref:c5]."
    assert check_report(report, plan(), facts, facts, rules) == []


def test_a_report_without_a_citation_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    assert kinds(check_report("Minggu ini kamu menjawab 12 kuis.", plan(), facts, facts, rules)) == {"missing_citation"}


def test_a_citation_to_something_not_in_the_facts_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    report = "Minggu ini kamu menjawab 12 kuis [ref:activity] [ref:invented]."
    assert kinds(check_report(report, plan(), facts, facts, rules)) == {"unknown_citation"}


def test_citing_a_note_the_learner_has_since_removed_is_a_stale_claim(rules: Rules) -> None:
    facts, fresh = sample_facts(notes=("note-1",)), sample_facts(notes=())
    report = "Kamu sering salah membaca [ref:note-1]."
    assert kinds(check_report(report, plan(), facts, fresh, rules)) == {"stale_claim"}


def test_citing_a_mistake_answered_since_is_a_stale_claim(rules: Rules) -> None:
    facts, fresh = sample_facts(mistakes=("m1",)), sample_facts(mistakes=())
    report = "Ulangi kata ini [ref:m1]."
    assert kinds(check_report(report, plan(review_word_ids=[]), facts, fresh, rules)) == {"stale_claim"}


@pytest.mark.guardrail("pipeline.report_max_words")
def test_a_report_over_the_word_limit_is_blocked(rules: Rules) -> None:
    facts = sample_facts()
    long_report = GOOD_REPORT + " kata" * rules.pipeline.report_max_words
    assert kinds(check_report(long_report, plan(), facts, facts, rules)) == {"too_long"}


# --- approval: Pitstop's decideApproval, plus code's issues ---


def review(grade: str | None, *issues: Issue) -> Review:
    return Review.model_validate({"grade": grade, "issues": [issue.model_dump() for issue in issues], "feedback": ""})


def test_a_clean_review_approves() -> None:
    assert decide_approval(review("A"), []).is_approved


def test_medium_and_low_issues_approve_with_notes() -> None:
    decision = decide_approval(review("B", Issue(reason="x", severity="medium"), Issue(reason="y", severity="low")), [])
    assert decision.is_approved and "1 medium" in decision.reason and "1 low" in decision.reason


def test_a_high_issue_from_tadashi_blocks() -> None:
    assert not decide_approval(review("B", Issue(reason="x", severity="high")), []).is_approved


def test_a_high_issue_from_code_blocks_even_when_tadashi_approves() -> None:
    decision = decide_approval(review("A"), [Issue(reason="x", source="code", kind="number_not_in_facts")])
    assert not decision.is_approved and "number_not_in_facts" in decision.reason


@pytest.mark.parametrize("grade", ["D", "F", None])
def test_a_low_grade_or_no_grade_blocks(grade: str | None) -> None:
    assert not decide_approval(review(grade), []).is_approved


def test_no_review_at_all_blocks() -> None:
    assert not decide_approval(None, []).is_approved
