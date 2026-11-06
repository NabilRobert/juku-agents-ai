"""Shiori behind AI Flight School's chat contract, for its scripted run (Flight School's slice 6). $0.

Flight School tests an agent that keeps its own tools (its observer adapter, A3): each turn it POSTs
an `ObservedChatRequest` (flight_school/http/contract.py) and checks the tool calls in the gateway's
audit log and the replies against its rules. This server answers each turn by calling
`juku_app.chat.ask` for the learner the request is signed in as, on the eval stack: throwaway
databases, Juku's MCP server, and the pinned gateway in front of it, so every tool call Shiori makes
is in the gateway's audit log.

The model is scripted (`scripted_shiori`): it picks a tool from the question's words and never
repeats what a tool returned, so it proves the plumbing only. A real model's run is a paid one and
needs Arthur's OK. Shiori keeps no memory between turns, so only each turn's last line is asked.

Run it, then point Flight School at the URL and audit log it prints:

    uv run python evals/flight_school_server.py --port 8765
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from unittest import mock

import uvicorn
from eval_gateway import GATEWAY_REF
from eval_stack import AllowAll, Stack, eval_rules, running_stack
from fastapi import FastAPI, HTTPException
from juku_app.budget import BudgetGuard
from juku_app.chat import ChatServices, ask
from juku_app.shiori import build_shiori, juku_toolset
from juku_data.engine.models import Learner
from juku_testkit.databases import repo_root
from juku_testkit.memory_fixtures import fixture_now, load_memory_fixture, source_of
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

sys.path.insert(0, str(repo_root() / "app" / "tests"))

from pipeline_helpers import consented  # pyright: ignore[reportMissingImports]  (on sys.path above)

# The learners Flight School's scenarios sign in as (its examples/shiori/world.yaml), by fixture name.
FIXTURE_LEARNERS = ("joko", "oka", "gita", "hana", "wulan")
DEFAULT_PORT = 8765
# The scripted Shiori's routes: a word in the question, and the one tool it calls. First match wins.
TOOL_FOR_WORDS = (
    ("kuasai", "get_progress"),
    ("rencana", "request_replan"),
    ("ingat", "get_memory"),
    ("salah baca", "get_memory"),
)
TOOL_REPLIES = {
    "get_progress": "Ini kemajuanmu dari datamu.",
    "request_replan": "Aku sudah meminta satu rencana baru untukmu.",
    "get_memory": "Ini catatan tentang cara belajarmu.",
}
NO_TOOL_REPLY = "Sama-sama! Sampai jumpa."


class ChatMessage(BaseModel):
    speaker: Literal["customer", "agent"]
    text: str


class ObservedChatRequest(BaseModel):
    """Flight School's turn for an observed agent, as in its flight_school/http/contract.py."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    signed_in_as: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str


def tool_for(question: str) -> str | None:
    lowered = question.lower()
    for words, tool in TOOL_FOR_WORDS:
        if words in lowered:
            return tool
    return None


def scripted_shiori(question: str) -> FunctionModel:
    """One tool call chosen from the question's words, then a fixed reply that quotes nothing it read."""
    tool = tool_for(question)

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        has_called = any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts)
        if tool is None:
            return ModelResponse(parts=[TextPart(NO_TOOL_REPLY)])
        if has_called:
            return ModelResponse(parts=[TextPart(TOOL_REPLIES[tool])])
        return ModelResponse(parts=[ToolCallPart(tool_name=tool, args={})])

    return FunctionModel(step)


async def load_learners(stack: Stack, names: Sequence[str] = FIXTURE_LEARNERS, suffix: str = "") -> dict[str, Learner]:
    """Each fixture learner, signed up and on the current consent notice, by public ID."""
    learners: dict[str, Learner] = {}
    for name in names:
        loaded = await load_memory_fixture(stack.db, stack.rules, name, suffix=suffix, source=source_of(name))
        learner = await consented(stack.db, loaded.learner)
        learners[learner.public_id] = learner
    return learners


def create_app(stack: Stack, learners: dict[str, Learner], now: datetime) -> FastAPI:
    app = FastAPI(title="Shiori for AI Flight School")

    @app.post("/chat")
    async def chat(turn: ObservedChatRequest) -> ChatResponse:  # pyright: ignore[reportUnusedFunction]
        learner = learners.get(turn.signed_in_as)
        if learner is None:
            known = ", ".join(sorted(learners))
            raise HTTPException(404, f"no learner {turn.signed_in_as!r} here: sign in as one of {known}")
        question = turn.messages[-1].text
        services = ChatServices(
            agent=build_shiori(
                scripted_shiori(question), juku_toolset(stack.mcp_url, stack.gateway_keys.get("shiori"))
            ),
            guard=BudgetGuard(stack.db.app, stack.rules),
            moderator=AllowAll(),
            signer=stack.signer,
            app=stack.db.app,
        )
        answer = await ask(services, learner, question, now)
        return ChatResponse(reply=answer.text)

    return app


async def serve(port: int) -> None:
    now = fixture_now()
    async with running_stack(eval_rules(with_gateway=True), gateway_ref=GATEWAY_REF) as stack:
        learners = await load_learners(stack)
        where = {"chat_url": f"http://127.0.0.1:{port}/chat", "audit_log": str(stack.gateway_audit_log)}
        print(json.dumps(where), flush=True)
        server = uvicorn.Server(uvicorn.Config(create_app(stack, learners, now), port=port, log_level="warning"))
        with mock.patch("juku_mcp.server.utc_now", lambda: now):  # the tools see the fixtures' week
            await server.serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shiori behind AI Flight School's chat contract, on a scripted model.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    asyncio.run(serve(parser.parse_args().port))
