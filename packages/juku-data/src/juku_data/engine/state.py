"""One word's state for one learner, and how each event changes it (LE1, LE6).

These are pure functions: the incremental path (engine/writes.py) applies
them as each event arrives, and the full recompute (engine/recompute.py)
derives the same state from the events in SQL, independently. Fitness
function FF3 checks the two agree.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

# LE6: Leitner boxes 1-5, each with a fixed wait before the word is due
# again; the wait doubles with each box.
LEITNER_INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
FIRST_BOX, LAST_BOX = 1, 5
# LE1: a word is known after correct answers on this many separate days,
# counted in the learner's own timezone.
CORRECT_DAYS_TO_KNOW = 2


@dataclass(frozen=True)
class ItemState:
    is_known: bool = False
    correct_days: int = 0
    last_correct_day: date | None = None
    correct_count: int = 0
    wrong_count: int = 0
    box: int | None = None
    due_at: datetime | None = None
    last_seen_at: datetime | None = None


def _next_box(box: int | None, is_correct: bool) -> int | None:
    """Wrong: back to box 1. Right: up a box, if the word is in the queue at all."""
    if not is_correct:
        return FIRST_BOX
    if box is None:
        return None
    return min(box + 1, LAST_BOX)


def after_quiz_answer(state: ItemState, *, is_correct: bool, at: datetime, local_day: date) -> ItemState:
    box = _next_box(state.box, is_correct)
    due_at = at + timedelta(days=LEITNER_INTERVAL_DAYS[box]) if box is not None else None
    correct_days, last_correct_day = state.correct_days, state.last_correct_day
    if is_correct and local_day != state.last_correct_day:
        correct_days, last_correct_day = correct_days + 1, local_day
    return replace(
        state,
        is_known=state.is_known or correct_days >= CORRECT_DAYS_TO_KNOW,
        correct_days=correct_days,
        last_correct_day=last_correct_day,
        correct_count=state.correct_count + (1 if is_correct else 0),
        wrong_count=state.wrong_count + (0 if is_correct else 1),
        box=box,
        due_at=due_at,
        last_seen_at=at,
    )


def after_marked_known(state: ItemState, *, at: datetime) -> ItemState:
    return replace(state, is_known=True, last_seen_at=at)


def after_unmarked_known(state: ItemState, *, at: datetime) -> ItemState:
    """Unknown again, and the count of correct days starts over (MEM-R5, LE1)."""
    return replace(state, is_known=False, correct_days=0, last_correct_day=None, last_seen_at=at)
