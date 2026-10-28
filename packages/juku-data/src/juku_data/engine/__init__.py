"""The learning engine (Phase 2 LE1-LE6, ADR-010): deterministic code over the learner's summaries.

Every function takes the two databases and an internal learner ID, and
returns a typed model. The read functions touch only the summaries, never
the event history (fitness function FF2); the write functions append an
event and update the summaries in the same transaction.
"""

from juku_data.engine.api import (
    Databases,
    LearnerNotFoundError,
    UnknownWordError,
    create_learner,
    find_reading_sentences,
    get_learner,
    get_mistakes,
    get_plan,
    get_progress,
    get_recent_activity,
    grade_answer,
    make_quiz,
    mark_known,
    rebuild_learner,
    recommend_words,
    record_sentence_read,
    set_target_level,
    set_timezone,
    unmark_known,
    verify_state,
)

__all__ = [
    "Databases",
    "LearnerNotFoundError",
    "UnknownWordError",
    "create_learner",
    "find_reading_sentences",
    "get_learner",
    "get_mistakes",
    "get_plan",
    "get_progress",
    "get_recent_activity",
    "grade_answer",
    "make_quiz",
    "mark_known",
    "rebuild_learner",
    "recommend_words",
    "record_sentence_read",
    "set_target_level",
    "set_timezone",
    "unmark_known",
    "verify_state",
]
