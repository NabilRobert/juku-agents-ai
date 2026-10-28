"""Juku's MCP server: the learner's data, read-only, scoped by the token in each request's `_meta`.

ADR-006 and ADR-018, on the MCP SDK's low-level server, which hands each
call's `_meta` to the handler. For every call, in order:
1. the tool must exist;
2. the delegation token in `_meta` must verify for this tool, and (behind
   the gateway) its acting agent must be the caller the gateway stamped;
3. the arguments must be exactly the tool's: nothing that names a learner;
4. the learner is the token's subject, looked up by public ID.
Only then does the tool run, through the learning engine.

Every call, allowed or refused, is one line in the hash-chained audit log
(SM5) and one span, neither holding the arguments or the result. A
refusal returns an error result with its category, never data.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from juku_common.audit_chain import AuditLog
from juku_common.delegation import AGENT_PREFIX, CALLER_META_KEY, META_KEY, Grant, RefusedError, Verifier
from juku_common.rules import Rules
from juku_data import engine
from juku_data.engine import Databases, LearnerNotFoundError
from mcp.server import Server, ServerRequestContext
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, PaginatedRequestParams, TextContent, Tool
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from juku_mcp.telemetry import tracer
from juku_mcp.tools import MAX_QUERY_LENGTH, SPECS, SPECS_BY_NAME, ToolCall, local_day, utc_now

SERVER_NAME = "juku"
MEMORY_PENDING = "Memory notes arrive in slice 4; none are stored yet."
REPLAN_QUEUED = "Permintaan rencana baru sudah dikirim ke Keiko. Rencananya tetap diperiksa sebelum ditampilkan."
REPLAN_LIMIT = "Hari ini sudah ada permintaan rencana baru. Coba lagi besok."

__all__ = ["ServerDeps", "WordSearch", "build_server", "local_day"]


class WordSearch(Protocol):
    async def search(self, query: str) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ServerDeps:
    db: Databases
    verifier: Verifier
    audit: AuditLog
    rules: Rules
    words: WordSearch


def _check_arguments(tool: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Exactly the tool's arguments: identity comes from the token, never from here (SM2)."""
    given = dict(arguments or {})
    expected = set(SPECS_BY_NAME[tool].input_schema["properties"])
    unexpected = sorted(set(given) - expected)
    if unexpected:
        raise RefusedError(
            "unexpected_arguments", f"unexpected arguments {unexpected}: the learner comes from the token"
        )
    if tool == "search_words":
        query = given.get("query")
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_LENGTH:
            raise RefusedError("bad_arguments", f"query must be 1 to {MAX_QUERY_LENGTH} characters of text")
    return given


async def _queue_replan(deps: ServerDeps, call: ToolCall) -> dict[str, Any]:
    """SM4: queue a Keiko run, at most `replan.max_requests_per_day` a learner's day."""
    day = local_day(call.now, call.learner.timezone)
    cap = deps.rules.replan.max_requests_per_day
    try:
        async with deps.db.app.begin() as connection:
            already = int(
                await connection.scalar(
                    text("SELECT count(*) FROM learning.replan_requests WHERE learner_id = :id AND local_day = :day"),
                    {"id": call.learner.id, "day": day},
                )
                or 0
            )
            if already >= cap:
                return {"queued": False, "message": REPLAN_LIMIT}
            await connection.execute(
                text(
                    "INSERT INTO learning.replan_requests (learner_id, local_day, sequence_in_day, actor_chain) "
                    "VALUES (:id, :day, :sequence, :chain)"
                ),
                {"id": call.learner.id, "day": day, "sequence": already + 1, "chain": list(call.chain)},
            )
    except IntegrityError:  # two requests at once: the unique key let one through
        return {"queued": False, "message": REPLAN_LIMIT}
    return {"queued": True, "message": REPLAN_QUEUED}


def _today(call: ToolCall) -> date:
    return local_day(call.now, call.learner.timezone)


def _handlers(deps: ServerDeps) -> dict[str, Callable[[ToolCall], Awaitable[dict[str, Any]]]]:
    db = deps.db

    async def progress(call: ToolCall) -> dict[str, Any]:
        return (await engine.get_progress(db, call.learner.id)).model_dump(mode="json")

    async def mistakes(call: ToolCall) -> dict[str, Any]:
        return (await engine.get_mistakes(db, call.learner.id, call.now)).model_dump(mode="json")

    async def recommendations(call: ToolCall) -> dict[str, Any]:
        return (await engine.recommend_words(db, call.learner.id)).model_dump(mode="json")

    async def reading(call: ToolCall) -> dict[str, Any]:
        return (await engine.find_reading_sentences(db, call.learner.id)).model_dump(mode="json")

    async def plan(call: ToolCall) -> dict[str, Any]:
        return (await engine.get_plan(db, call.learner.id, _today(call))).model_dump(mode="json")

    async def activity(call: ToolCall) -> dict[str, Any]:
        return (await engine.get_recent_activity(db, call.learner.id, _today(call))).model_dump(mode="json")

    async def memory(_: ToolCall) -> dict[str, Any]:
        return {"notes": [], "status": MEMORY_PENDING}

    async def search(call: ToolCall) -> dict[str, Any]:
        return {"words": await deps.words.search(str(call.arguments["query"]))}

    async def replan(call: ToolCall) -> dict[str, Any]:
        return await _queue_replan(deps, call)

    return {
        "get_progress": progress,
        "get_mistakes": mistakes,
        "recommend_words": recommendations,
        "find_reading_sentences": reading,
        "get_plan": plan,
        "get_recent_activity": activity,
        "get_memory": memory,
        "search_words": search,
        "request_replan": replan,
    }


def _result(body: dict[str, Any], *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(body, ensure_ascii=False))],
        structured_content=body,
        is_error=is_error,
    )


def build_server(deps: ServerDeps) -> Server[Any]:
    handlers = _handlers(deps)
    listed = [Tool(name=spec.name, description=spec.description, input_schema=spec.input_schema) for spec in SPECS]
    assert set(handlers) == set(SPECS_BY_NAME), "every tool needs a handler"

    async def list_tools(_: ServerRequestContext[Any], __: PaginatedRequestParams | None) -> ListToolsResult:
        return ListToolsResult(tools=listed)

    async def authorize(params: CallToolRequestParams, meta: dict[str, Any]) -> tuple[Grant, ToolCall]:
        if params.name not in SPECS_BY_NAME:
            raise RefusedError("unknown_tool", f"no tool called {params.name!r}")
        token, caller = meta.get(META_KEY), meta.get(CALLER_META_KEY)
        grant = deps.verifier.verify(
            token if isinstance(token, str) else None,
            params.name,
            caller=caller if isinstance(caller, str) else None,
        )
        arguments = _check_arguments(params.name, params.arguments)
        try:
            learner = await engine.get_learner(deps.db, grant.learner)
        except LearnerNotFoundError as exc:
            raise RefusedError("unknown_learner", "the token's learner doesn't exist") from exc
        return grant, ToolCall(learner=learner, chain=grant.chain, arguments=arguments, now=utc_now())

    async def call_tool(_: ServerRequestContext[Any], params: CallToolRequestParams) -> CallToolResult:
        meta: dict[str, Any] = dict(params.meta or {})
        caller = meta.get(CALLER_META_KEY)
        record: dict[str, Any] = {"tool": params.name, "caller": caller if isinstance(caller, str) else None}
        with tracer.start_as_current_span(f"juku.tool_call {params.name}") as span:
            span.set_attribute("juku.tool", params.name)
            try:
                grant, call = await authorize(params, meta)
            except RefusedError as refusal:
                span.set_attribute("juku.decision", "refused")
                span.set_attribute("juku.reason_category", refusal.category)
                deps.audit.append(
                    "call", **record, decision="refused", reason_category=refusal.category, reason=str(refusal)
                )
                return _result({"refused": refusal.category, "message": str(refusal)}, is_error=True)
            span.set_attribute("juku.decision", "allowed")
            span.set_attribute("juku.agent", grant.agent)
            span.set_attribute("juku.chain_length", len(grant.chain))
            deps.audit.append(
                "call",
                **record,
                decision="allowed",
                actor_chain=[f"{AGENT_PREFIX}{agent}" for agent in grant.chain],
                learner=grant.learner,
                purpose=grant.purpose,
                run=grant.run,
                jti=grant.jti,
            )
            return _result(await handlers[params.name](call))

    return Server(SERVER_NAME, on_list_tools=list_tools, on_call_tool=call_tool)
