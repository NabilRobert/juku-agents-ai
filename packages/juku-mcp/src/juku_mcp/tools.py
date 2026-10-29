"""The tools Juku's MCP server offers: their contract, and what each one runs.

No tool takes a learner (SM2): the learner is the verified token's
subject. Only search_words takes an argument, the query. Every read goes
through the learning engine, which reads the summaries only (FF2).
Changing a name, description or schema here must change
tests/snapshots/tools.json in the same commit (FF5).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from juku_data.engine.models import Learner

NO_ARGUMENTS: dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
SEARCH_ARGUMENTS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "What to look up, e.g. 食べる, たべる, taberu or to eat."},
    },
    "required": ["query"],
    "additionalProperties": False,
}
MAX_QUERY_LENGTH = 64


def local_day(at: datetime, timezone: str) -> date:
    """The learner's own date at this moment."""
    return at.astimezone(ZoneInfo(timezone)).date()


@dataclass(frozen=True)
class ToolCall:
    """What a handler gets: the learner the token names, the verified chain, the checked arguments."""

    learner: Learner
    chain: tuple[str, ...]
    arguments: dict[str, Any]
    now: datetime


Handler = Callable[[Any, ToolCall], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


SPECS = [
    ToolSpec(
        "get_progress",
        "The learner's progress: how many words they know, and their coverage of each JLPT level's words and kanji "
        "(N5 to N1).",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "get_mistakes",
        "The learner's mistakes queue (Leitner boxes 1-5): words they answered wrongly, with when each is due for "
        "review.",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "recommend_words",
        "Ten words for the learner to learn next, from Juku's recommender (Susumu), each with the reason it was "
        "chosen. Facts only; don't invent other suggestions.",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "find_reading_sentences",
        "Up to ten example sentences (from Tatoeba, with furigana) in which the learner knows every word but one, and "
        "that one new word.",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "get_plan",
        "The learner's pace plan: the words a week needed to reach 80% of their target level and everything easier "
        "by their exam date, with the formula.",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "get_recent_activity",
        "The learner's activity over the last 7 days, by their local date: quiz answers, correct answers, words "
        "marked known, sentences read.",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "get_memory",
        "What Shiori remembers about how this learner learns: notes with their evidence. Read-only.",
        NO_ARGUMENTS,
    ),
    ToolSpec(
        "search_words",
        "Search the JLPT dictionary (OpenJLPT) by kanji, kana, romaji or English. Returns up to ten words with their "
        "ID, reading, level and meanings. Contains no learner data.",
        SEARCH_ARGUMENTS,
    ),
    ToolSpec(
        "request_replan",
        "Ask Keiko, the planner, for a new weekly plan for this learner. It only queues a run (at most one a day); "
        "the plan still passes the critic and code, and the learner decides whether to use it.",
        NO_ARGUMENTS,
    ),
]
SPECS_BY_NAME = {spec.name: spec for spec in SPECS}


def utc_now() -> datetime:
    return datetime.now(UTC)
