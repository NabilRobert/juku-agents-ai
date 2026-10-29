"""One agent tool call to Juku's MCP server, with its per-call record (Phase 2 M1): shared by Shiori and Keiko.

Each call carries the token the agent minted for it in `_meta`; its
result is kept on the run (for the citation check, or Keiko's run); and
one row goes to monitoring.tool_calls: agent, chain, tool, duration,
outcome, rows and trace ID, never the arguments or the result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from juku_common.delegation import META_KEY
from opentelemetry import trace
from pydantic_ai.mcp import CallToolFunc
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

SERVER = "juku"
RECORD_CALL = """
INSERT INTO monitoring.tool_calls (called_at, agent, server, tool, duration_ms, outcome, error_category,
                                   row_count, trace_id, actor_chain, learner_id)
VALUES (:called_at, :agent, :server, :tool, :duration_ms, :outcome, :error_category,
        :row_count, :trace_id, :actor_chain, :learner_id)
"""


@dataclass(frozen=True)
class ToolCaller:
    """Who makes a run's tool calls, for their records; `results` is the run's own list, which each result joins."""

    agent: str
    chain: tuple[str, ...]
    learner_id: int
    records: AsyncEngine
    results: list[Any]


def row_count(body: Any) -> int | None:
    """How many rows a tool returned: the length of its first list."""
    if isinstance(body, dict):
        for value in cast(dict[str, Any], body).values():
            if isinstance(value, list):
                return len(cast(list[Any], value))
    return None


def current_trace_id() -> str | None:
    context = trace.get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def refusal_category(message: str) -> str | None:
    """Juku's refusal category, from the error text a refused call raises with."""
    marker = '"refused": "'
    start = message.find(marker)
    if start < 0:
        return None
    start += len(marker)
    return message[start : message.find('"', start)]


async def record_call(
    caller: ToolCaller, tool: str, started: float, *, rows: int | None = None, error: BaseException | None = None
) -> None:
    """The per-call record: ok, or refused (with Juku's category), or a tool error (with the exception's name)."""
    category = refusal_category(str(error)) if error is not None else None
    if error is None:
        outcome, error_category = "ok", None
    else:
        outcome, error_category = ("refused", category) if category else ("tool_error", type(error).__name__)
    async with caller.records.begin() as connection:
        await connection.execute(
            text(RECORD_CALL),
            {
                "called_at": datetime.now(UTC),
                "agent": caller.agent,
                "server": SERVER,
                "tool": tool,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "outcome": outcome,
                "error_category": error_category,
                "row_count": rows,
                "trace_id": current_trace_id(),
                "actor_chain": list(caller.chain),
                "learner_id": caller.learner_id,
            },
        )


async def call_and_record(
    caller: ToolCaller, call_tool: CallToolFunc, name: str, arguments: dict[str, Any], token: str
) -> Any:
    """One MCP call with `token` in its `_meta`: the result kept, the call recorded, whatever happens."""
    started = time.perf_counter()
    try:
        result = await call_tool(name, arguments, metadata={META_KEY: token})
    except Exception as error:
        await record_call(caller, name, started, error=error)
        raise
    caller.results.append(result)
    await record_call(caller, name, started, rows=row_count(result))
    return result
