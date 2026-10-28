"""The rules a proposed note must pass, and the weekly keep-or-lapse decision (MEM-R2 to MEM-R4), as pure functions."""

from datetime import UTC, datetime, timedelta

import pytest
from juku_common.rules import MemoryRules, Rules
from juku_data.memory.evidence import (
    CONTRADICTED,
    EVIDENCE_NOT_FOUND,
    EVIDENCE_NOT_THIS_LEARNERS,
    EVIDENCE_RECENT,
    EVIDENCE_TOO_OLD,
    FORBIDDEN_CATEGORY,
    FORBIDDEN_CONTENT,
    NO_PATTERN,
    RECURRED,
    TEXT_TOO_LONG,
    TOO_LITTLE_EVIDENCE,
    UNKNOWN_CATEGORY,
    EvidenceRow,
    check_category,
    check_evidence,
    check_text,
    consolidation_decision,
    shows_pattern,
)

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
LEARNER = 7


@pytest.fixture
def memory(rules: Rules) -> MemoryRules:
    return rules.memory


def row(
    event_id: int,
    event_type: str,
    *,
    days_ago: float = 1,
    item: str = "w1",
    level: int | None = 5,
    is_correct: bool | None = None,
    learner_id: int = LEARNER,
) -> EvidenceRow:

    return EvidenceRow(
        event_id=event_id,
        learner_id=learner_id,
        event_type=event_type,
        item_id=item,
        level=level,
        is_correct=is_correct,
        occurred_at=NOW - timedelta(days=days_ago),
    )


def misses(kind: str = "quiz_reading", item: str = "w1", start: int = 1, days_ago: float = 1) -> list[EvidenceRow]:
    return [row(start + offset, kind, item=item, is_correct=False, days_ago=days_ago + offset) for offset in range(3)]


# --- categories and text (MEM-R3) ---


@pytest.mark.guardrail("memory.forbidden_categories")
@pytest.mark.parametrize("category", ["health", "emotions", "personal_life", "work", "other_people"])
def test_a_note_about_life_rather_than_learning_is_refused_as_forbidden(memory: MemoryRules, category: str) -> None:
    assert check_category(category, memory) == FORBIDDEN_CATEGORY


@pytest.mark.guardrail("memory.allowed_categories")
def test_only_the_learning_categories_are_allowed(memory: MemoryRules) -> None:
    for category in ("recurring_confusion", "preferred_example", "pace", "avoided_level"):
        assert check_category(category, memory) is None
    assert check_category("favourite_food", memory) == UNKNOWN_CATEGORY


@pytest.mark.guardrail("memory.forbidden_text_markers")
@pytest.mark.parametrize("text", ["Belajar pelan karena SAKIT.", "Belajar setelah pulang kerja.", "Sering sedih."])
def test_a_learning_category_with_text_about_life_is_refused(memory: MemoryRules, text: str) -> None:
    assert check_text(text, memory) == FORBIDDEN_CONTENT


@pytest.mark.guardrail("memory.max_text_chars")
def test_a_note_longer_than_the_limit_is_refused(memory: MemoryRules) -> None:
    assert check_text("a" * (memory.max_text_chars + 1), memory) == TEXT_TOO_LONG
    assert check_text("a" * memory.max_text_chars, memory) is None


# --- the pattern each category's evidence must show (MEM-R2) ---


def test_three_wrong_answers_of_one_quiz_kind_show_a_confusion() -> None:
    assert shows_pattern("recurring_confusion", misses())


def test_wrong_answers_of_two_quiz_kinds_dont_show_one_confusion() -> None:
    mixed = [*misses()[:2], row(9, "quiz_meaning", is_correct=False)]
    assert not shows_pattern("recurring_confusion", mixed)


def test_a_right_answer_among_the_evidence_shows_no_confusion() -> None:
    rows = [*misses()[:2], row(9, "quiz_reading", is_correct=True)]
    assert not shows_pattern("recurring_confusion", rows)


def test_sentences_read_show_a_preference_for_examples() -> None:
    assert shows_pattern("preferred_example", [row(n, "sentence_read", item=str(n), level=None) for n in range(3)])
    assert not shows_pattern("preferred_example", [*misses()[:2], row(9, "sentence_read")])


def test_pace_needs_words_marked_on_at_least_two_days() -> None:
    same_day = [row(n, "marked_known", item=str(n), days_ago=1) for n in range(3)]
    two_days = [row(n, "marked_known", item=str(n), days_ago=1 + n % 2) for n in range(3)]
    assert not shows_pattern("pace", same_day)
    assert shows_pattern("pace", two_days)


def test_an_avoided_level_needs_misses_or_unmarks_all_at_one_level() -> None:
    one_level = [
        row(1, "unmarked_known", level=3),
        *[row(n, "quiz_meaning", level=3, is_correct=False) for n in (2, 3)],
    ]
    two_levels = [*one_level[:2], row(4, "unmarked_known", level=2)]
    unknown_level = [*one_level[:2], row(4, "unmarked_known", level=None)]
    assert shows_pattern("avoided_level", one_level)
    assert not shows_pattern("avoided_level", two_levels)
    assert not shows_pattern("avoided_level", unknown_level)


# --- the evidence itself (MEM-R2) ---


def test_evidence_that_doesnt_exist_is_refused(memory: MemoryRules) -> None:
    rows = misses()
    assert check_evidence("recurring_confusion", [1, 2, 3, 99], rows, LEARNER, memory, NOW) == EVIDENCE_NOT_FOUND
    assert check_evidence("recurring_confusion", [], [], LEARNER, memory, NOW) == EVIDENCE_NOT_FOUND


def test_another_learners_evidence_is_refused(memory: MemoryRules) -> None:
    rows = [*misses()[:2], row(3, "quiz_reading", is_correct=False, learner_id=LEARNER + 1)]
    assert check_evidence("recurring_confusion", [1, 2, 3], rows, LEARNER, memory, NOW) == EVIDENCE_NOT_THIS_LEARNERS


@pytest.mark.guardrail("memory.min_evidence_events")
def test_fewer_rows_than_the_minimum_are_too_little_evidence(memory: MemoryRules) -> None:
    rows = misses()[: memory.min_evidence_events - 1]
    ids = [r.event_id for r in rows]
    assert check_evidence("recurring_confusion", ids, rows, LEARNER, memory, NOW) == TOO_LITTLE_EVIDENCE


def test_evidence_that_doesnt_show_the_category_is_refused(memory: MemoryRules) -> None:
    assert check_evidence("pace", [1, 2, 3], misses(), LEARNER, memory, NOW) == NO_PATTERN


@pytest.mark.guardrail("memory.evidence_max_age_days")
def test_evidence_older_than_the_window_is_refused(memory: MemoryRules) -> None:
    old = misses(days_ago=memory.evidence_max_age_days + 1)
    assert check_evidence("recurring_confusion", [1, 2, 3], old, LEARNER, memory, NOW) == EVIDENCE_TOO_OLD


def test_good_evidence_passes(memory: MemoryRules) -> None:
    assert check_evidence("recurring_confusion", [1, 2, 3], misses(), LEARNER, memory, NOW) is None


# --- consolidation (MEM-R4) ---


def test_a_note_with_recent_evidence_is_kept(memory: MemoryRules) -> None:
    assert consolidation_decision("recurring_confusion", misses(), [], memory, NOW) == ("kept", EVIDENCE_RECENT)


@pytest.mark.guardrail("memory.evidence_max_age_days")
def test_a_note_whose_evidence_is_over_the_window_and_hasnt_recurred_lapses(memory: MemoryRules) -> None:
    old = misses(days_ago=memory.evidence_max_age_days + 1)
    assert consolidation_decision("recurring_confusion", old, [], memory, NOW) == ("lapsed", EVIDENCE_TOO_OLD)


def test_a_note_that_recurred_is_kept_however_old_its_first_evidence(memory: MemoryRules) -> None:
    old = misses(days_ago=memory.evidence_max_age_days + 5)
    again = [row(20, "quiz_reading", is_correct=False, days_ago=2)]
    assert consolidation_decision("recurring_confusion", old, again, memory, NOW) == ("kept", RECURRED)


def test_a_miss_on_another_word_isnt_a_recurrence(memory: MemoryRules) -> None:
    old = misses(days_ago=memory.evidence_max_age_days + 5)
    other_word = [row(20, "quiz_reading", item="w2", is_correct=False, days_ago=2)]
    assert consolidation_decision("recurring_confusion", old, other_word, memory, NOW) == ("lapsed", EVIDENCE_TOO_OLD)


@pytest.mark.guardrail("memory.contradicting_answers")
def test_a_confusion_answered_right_enough_times_since_lapses_as_contradicted(memory: MemoryRules) -> None:
    right = [row(20 + n, "quiz_reading", is_correct=True, days_ago=0.5) for n in range(memory.contradicting_answers)]
    assert consolidation_decision("recurring_confusion", misses(), right, memory, NOW) == ("lapsed", CONTRADICTED)
    too_few = right[: memory.contradicting_answers - 1]
    assert consolidation_decision("recurring_confusion", misses(), too_few, memory, NOW)[0] == "kept"


def test_right_answers_before_a_newer_miss_dont_contradict_it(memory: MemoryRules) -> None:
    right_then_wrong = [
        *[row(20 + n, "quiz_reading", is_correct=True, days_ago=0.9) for n in range(memory.contradicting_answers)],
        row(30, "quiz_reading", is_correct=False, days_ago=0.5),
    ]
    assert consolidation_decision("recurring_confusion", misses(), right_then_wrong, memory, NOW) == ("kept", RECURRED)


# --- the gaps mutmut found (JOURNEY, slice 4) ---


def test_an_unknown_category_shows_no_pattern() -> None:
    assert not shows_pattern("favourite_food", misses())


def test_a_right_answer_at_the_level_is_not_avoidance() -> None:
    rows = [row(1, "unmarked_known", level=3), *[row(n, "quiz_meaning", level=3, is_correct=True) for n in (2, 3)]]
    assert not shows_pattern("avoided_level", rows)


def test_evidence_exactly_at_the_edge_of_the_window_is_still_recent(memory: MemoryRules) -> None:
    edge = [*misses(days_ago=memory.evidence_max_age_days)][:1]
    rows = [
        *edge,
        *[row(n, "quiz_reading", is_correct=False, days_ago=memory.evidence_max_age_days + 1) for n in (2, 3)],
    ]
    assert check_evidence("recurring_confusion", [1, 2, 3], rows, LEARNER, memory, NOW) is None


def test_a_note_exactly_at_the_edge_of_the_window_is_kept(memory: MemoryRules) -> None:
    edge = [row(n, "quiz_reading", is_correct=False, days_ago=memory.evidence_max_age_days + n - 1) for n in (1, 2, 3)]
    assert consolidation_decision("recurring_confusion", edge, [], memory, NOW)[0] == "kept"


def test_right_answers_on_another_word_or_of_another_kind_dont_contradict_a_confusion(memory: MemoryRules) -> None:
    other_word = [row(20 + n, "quiz_reading", item="w2", is_correct=True, days_ago=0.5) for n in range(3)]
    other_kind = [row(30 + n, "quiz_meaning", is_correct=True, days_ago=0.5) for n in range(3)]
    for newer in (other_word, other_kind):
        assert consolidation_decision("recurring_confusion", misses(), newer, memory, NOW)[0] == "kept"


def test_right_answers_never_contradict_the_other_categories(memory: MemoryRules) -> None:
    pace = [row(n, "marked_known", item=f"k{n}", days_ago=1 + n % 2) for n in range(3)]
    right = [row(20 + n, "quiz_meaning", item=f"k{n}", is_correct=True, days_ago=0.5) for n in range(3)]
    assert consolidation_decision("pace", pace, right, memory, NOW)[0] == "kept"


def test_a_wrong_answer_of_another_kind_on_the_same_word_is_not_a_recurrence(memory: MemoryRules) -> None:
    old = misses(days_ago=memory.evidence_max_age_days + 5)
    other_kind = [row(20, "quiz_meaning", is_correct=False, days_ago=2)]
    right = [row(21, "quiz_reading", is_correct=True, days_ago=2)]
    for newer in (other_kind, right):
        assert consolidation_decision("recurring_confusion", old, newer, memory, NOW) == ("lapsed", EVIDENCE_TOO_OLD)


@pytest.mark.parametrize(
    ("category", "evidence", "again", "elsewhere"),
    [
        (
            "preferred_example",
            [row(n, "sentence_read", item=str(n), level=None, days_ago=40 + n) for n in range(3)],
            row(20, "sentence_read", item="9", level=None, days_ago=2),
            row(21, "marked_known", item="k9", days_ago=2),
        ),
        (
            "pace",
            [row(n, "marked_known", item=f"k{n}", days_ago=40 + n) for n in range(3)],
            row(20, "marked_known", item="k9", days_ago=2),
            row(21, "sentence_read", item="9", level=None, days_ago=2),
        ),
        (
            "avoided_level",
            [row(n, "unmarked_known", item=f"u{n}", level=3, days_ago=40 + n) for n in range(3)],
            row(20, "quiz_meaning", item="u9", level=3, is_correct=False, days_ago=2),
            row(21, "unmarked_known", item="u8", level=2, days_ago=2),
        ),
    ],
)
def test_each_category_recurs_only_with_its_own_pattern(
    memory: MemoryRules, category: str, evidence: list[EvidenceRow], again: EvidenceRow, elsewhere: EvidenceRow
) -> None:
    assert consolidation_decision(category, evidence, [again], memory, NOW) == ("kept", RECURRED)
    assert consolidation_decision(category, evidence, [elsewhere], memory, NOW) == ("lapsed", EVIDENCE_TOO_OLD)


def test_an_unknown_category_never_recurs(memory: MemoryRules) -> None:
    old = misses(days_ago=memory.evidence_max_age_days + 5)
    anything = [row(20, "quiz_reading", is_correct=False, days_ago=2)]
    assert consolidation_decision("favourite_food", old, anything, memory, NOW) == ("lapsed", EVIDENCE_TOO_OLD)
