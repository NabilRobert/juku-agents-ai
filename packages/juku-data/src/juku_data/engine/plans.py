"""The hot queries the fitness functions explain (FF1, FF13).

Each entry names a query the engine runs on every page view or tool call,
the database it runs in, and whether an agent's tool runs it (FF13 then
also holds it under the JIT threshold). The SQL is the engine's own
constant, not a copy, so a change to a query is a change to what's
checked.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from juku_data.engine.quiz import DUE_ITEMS, IN_PROGRESS
from juku_data.engine.reads import ACTIVITY, COVERAGE, KNOWN_COUNT, KNOWN_IDS, MISTAKES, RANKED_CANDIDATES, READING


@dataclass(frozen=True)
class HotQuery:
    name: str
    database: Literal["app", "dictionary"]
    sql: str
    is_tool_query: bool


HOT_QUERIES = [
    HotQuery("recommend_words", "app", RANKED_CANDIDATES, is_tool_query=True),
    HotQuery("coverage", "app", COVERAGE, is_tool_query=True),
    HotQuery("known_count", "app", KNOWN_COUNT, is_tool_query=True),
    HotQuery("known_ids", "app", KNOWN_IDS, is_tool_query=True),
    HotQuery("mistakes", "app", MISTAKES, is_tool_query=True),
    HotQuery("recent_activity", "app", ACTIVITY, is_tool_query=True),
    HotQuery("reading_sentences", "dictionary", READING, is_tool_query=True),
    HotQuery("quiz_due_items", "app", DUE_ITEMS, is_tool_query=False),
    HotQuery("quiz_in_progress", "app", IN_PROGRESS, is_tool_query=False),
]
