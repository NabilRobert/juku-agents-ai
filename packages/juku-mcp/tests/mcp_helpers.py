"""Helpers for Juku's MCP server tests: two learners, a deps builder, and a typed way to call a tool."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.audit_chain import JUKU_MCP_GENESIS, AuditLog
from juku_common.delegation import CALLER_META_KEY, META_KEY, Signer, Verifier
from juku_common.rules import Rules, load_rules
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from juku_mcp.search import DictionarySearch
from juku_mcp.server import ServerDeps
from mcp import Client
from mcp.server import Server

ALL_SHIORI_TOOLS = [
    "get_progress",
    "get_mistakes",
    "recommend_words",
    "find_reading_sentences",
    "get_plan",
    "get_recent_activity",
    "get_memory",
    "search_words",
    "request_replan",
]


@dataclass
class Learners:
    a: Learner
    b: Learner


def direct_rules() -> Rules:
    """The rule file as the tests reach the server: directly, with no gateway stamping the caller."""
    rules = load_rules()
    return rules.model_copy(
        update={"delegation": rules.delegation.model_copy(update={"require_gateway_caller": False})}
    )


def make_deps(
    db: Databases, key: ed25519.Ed25519PrivateKey, audit_path: Path, rules: Rules | None = None
) -> ServerDeps:
    rules = rules or direct_rules()
    return ServerDeps(
        db=db,
        verifier=Verifier(key.public_key(), rules),
        audit=AuditLog(audit_path, genesis=JUKU_MCP_GENESIS, fsync=False),
        rules=rules,
        words=DictionarySearch(db.dictionary),
    )


@dataclass(frozen=True)
class Answer:
    is_error: bool
    body: dict[str, Any]
    text: str


async def call(
    client: Client,
    tool: str,
    token: str | None,
    arguments: dict[str, Any] | None = None,
    caller: str | None = None,
) -> Answer:
    meta: dict[str, Any] = {}
    if token is not None:
        meta[META_KEY] = token
    if caller is not None:
        meta[CALLER_META_KEY] = caller
    result = await client.call_tool(tool, arguments or {}, meta=meta)  # pyright: ignore[reportArgumentType]
    body: Any = result.structured_content or {}
    text_part = "".join(getattr(part, "text", "") for part in result.content)
    return Answer(is_error=bool(result.is_error), body=dict(body), text=text_part)


def token_for(signer: Signer, learner: Learner, tools: list[str] | None = None, agent: str = "shiori") -> str:
    return signer.mint(learner=learner.public_id, agent=agent, tools=tools or ALL_SHIORI_TOOLS, purpose="chat")


@asynccontextmanager
async def connected(server: Server[Any]) -> AsyncIterator[Client]:
    """A client on `server` in memory, opened and closed in one background task.

    anyio's cancel scopes must be left in the task that entered them, and
    pytest-asyncio sets a fixture up and tears it down in different tasks,
    so the client lives in a task of its own until the test is done.
    """
    ready, done = asyncio.Event(), asyncio.Event()
    holder: list[Client] = []

    async def hold_open() -> None:
        async with Client(server) as client:
            holder.append(client)
            ready.set()
            await done.wait()

    task = asyncio.create_task(hold_open())
    await asyncio.wait({task, asyncio.create_task(ready.wait())}, return_when=asyncio.FIRST_COMPLETED)
    if task.done():
        task.result()  # raise whatever stopped it
    try:
        yield holder[0]
    finally:
        done.set()
        await task
