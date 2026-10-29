"""LE1 and LE6 as pure rules: how one word's state changes with each event."""

from datetime import UTC, date, datetime, timedelta

from juku_data.engine.state import (
    ItemState,
    after_marked_known,
    after_quiz_answer,
    after_unmarked_known,
)

MONDAY = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def answer(state: ItemState, is_correct: bool, at: datetime) -> ItemState:
    return after_quiz_answer(state, is_correct=is_correct, at=at, local_day=at.date())


def test_one_correct_answer_does_not_make_a_word_known() -> None:
    state = answer(ItemState(), True, MONDAY)
    assert (state.is_known, state.correct_days, state.correct_count) == (False, 1, 1)


def test_two_correct_answers_on_one_day_count_as_one_day() -> None:
    state = answer(answer(ItemState(), True, MONDAY), True, MONDAY + timedelta(hours=5))
    assert (state.is_known, state.correct_days, state.correct_count) == (False, 1, 2)


def test_correct_answers_on_two_separate_days_make_a_word_known() -> None:
    state = answer(answer(ItemState(), True, MONDAY), True, MONDAY + timedelta(days=1))
    assert (state.is_known, state.correct_days, state.last_correct_day) == (True, 2, date(2026, 11, 3))


def test_the_local_day_decides_not_the_utc_day() -> None:
    first = after_quiz_answer(ItemState(), is_correct=True, at=MONDAY, local_day=date(2026, 11, 2))
    second = after_quiz_answer(first, is_correct=True, at=MONDAY + timedelta(hours=1), local_day=date(2026, 11, 3))
    assert second.is_known


def test_a_wrong_answer_puts_the_word_in_box_1_due_a_day_later() -> None:
    state = answer(ItemState(), False, MONDAY)
    assert (state.box, state.due_at, state.wrong_count) == (1, MONDAY + timedelta(days=1), 1)


def test_each_right_answer_moves_the_word_up_a_box_until_box_5() -> None:
    state = answer(ItemState(), False, MONDAY)
    boxes: list[tuple[int | None, timedelta | None]] = []
    for step in range(1, 6):
        at = MONDAY + timedelta(days=step)
        state = answer(state, True, at)
        boxes.append((state.box, state.due_at - at if state.due_at else None))
    assert boxes == [
        (2, timedelta(days=2)),
        (3, timedelta(days=4)),
        (4, timedelta(days=8)),
        (5, timedelta(days=16)),
        (5, timedelta(days=16)),
    ]


def test_a_wrong_answer_sends_the_word_back_to_box_1() -> None:
    state = answer(
        answer(answer(ItemState(), False, MONDAY), True, MONDAY + timedelta(days=1)), False, MONDAY + timedelta(days=3)
    )
    assert state.box == 1


def test_a_word_never_answered_wrongly_is_not_in_the_mistakes_queue() -> None:
    assert answer(ItemState(), True, MONDAY).box is None


def test_marking_a_word_known_keeps_its_counts() -> None:
    state = after_marked_known(answer(ItemState(), True, MONDAY), at=MONDAY + timedelta(hours=1))
    assert (state.is_known, state.correct_count, state.last_seen_at) == (True, 1, MONDAY + timedelta(hours=1))


def test_a_wrong_answer_does_not_unknow_a_known_word() -> None:
    state = answer(after_marked_known(ItemState(), at=MONDAY), False, MONDAY + timedelta(hours=1))
    assert (state.is_known, state.box) == (True, 1)


def test_unmarking_makes_the_word_unknown_and_resets_its_correct_days() -> None:
    known = answer(answer(ItemState(), True, MONDAY), True, MONDAY + timedelta(days=1))
    state = after_unmarked_known(known, at=MONDAY + timedelta(days=2))
    assert (state.is_known, state.correct_days, state.last_correct_day, state.correct_count) == (False, 0, None, 2)


def test_after_unmarking_two_new_correct_days_are_needed() -> None:
    state = after_unmarked_known(answer(ItemState(), True, MONDAY), at=MONDAY + timedelta(days=1))
    state = answer(state, True, MONDAY + timedelta(days=2))
    assert not state.is_known
    assert answer(state, True, MONDAY + timedelta(days=3)).is_known


def test_a_wrong_answer_counts_only_as_wrong_and_a_right_one_only_as_right() -> None:
    wrong = answer(ItemState(), False, MONDAY)
    right = answer(wrong, True, MONDAY + timedelta(days=1))
    assert (wrong.correct_count, wrong.wrong_count) == (0, 1)
    assert (right.correct_count, right.wrong_count) == (1, 1)


def test_every_event_records_when_the_word_was_last_seen() -> None:
    later = MONDAY + timedelta(hours=3)
    assert answer(ItemState(), True, MONDAY).last_seen_at == MONDAY
    assert after_unmarked_known(ItemState(), at=later).last_seen_at == later
    assert after_marked_known(ItemState(), at=later).last_seen_at == later
