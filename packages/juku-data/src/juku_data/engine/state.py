"""One word's state, and how each event changes it (stub: lands with the engine)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

# LE6: Leitner boxes 1-5, each with a fixed wait before the word is due again.
LEITNER_INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}
# LE1: a word is known after correct answers on this many separate local days.
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


def after_quiz_answer(state: ItemState, *, is_correct: bool, at: datetime, local_day: date) -> ItemState:
    raise NotImplementedError


def after_marked_known(state: ItemState, *, at: datetime) -> ItemState:
    raise NotImplementedError


def after_unmarked_known(state: ItemState, *, at: datetime) -> ItemState:
    raise NotImplementedError
