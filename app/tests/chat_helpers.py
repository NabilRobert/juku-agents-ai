"""Helpers for the tests of Shiori's chat: the services, a moderator that allows all, and a citing model."""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.budget import BudgetGuard
from juku_app.chat import ChatServices
from juku_app.moderation import Verdict
from juku_app.shiori import build_shiori, juku_toolset
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import Databases
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


class AllowAll:
    async def check(self, message: str) -> Verdict:
        assert message
        return Verdict(suggests_self_harm=False)


def services(
    model: Model, url: str, key: ed25519.Ed25519PrivateKey, db: Databases, moderator: Any = None
) -> ChatServices:
    rules = load_rules()
    return ChatServices(
        agent=build_shiori(model, juku_toolset(url)),
        guard=BudgetGuard(db.app, rules),
        moderator=moderator or AllowAll(),
        signer=Signer(key, rules),
        app=db.app,
    )


def tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [part for message in messages for part in getattr(message, "parts", []) if isinstance(part, ToolReturnPart)]


def citing(word_id: str | None) -> FunctionModel:
    """Asks for recommendations, then answers citing `word_id` (or the first word returned, if None)."""

    def answer_text(messages: list[ModelMessage]) -> str | None:
        returns = tool_returns(messages)
        if not returns:
            return None
        returned: Any = returns[-1].content
        body = returned if isinstance(returned, dict) else json.loads(str(returned))
        return f"Pelajari kata ini dulu [ref:{word_id or body['words'][0]['word_id']}]."

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        answer = answer_text(messages)
        if answer is None:
            return ModelResponse(parts=[ToolCallPart(tool_name="recommend_words", args={})])
        return ModelResponse(parts=[TextPart(answer)])

    async def stream(messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        answer = answer_text(messages)
        if answer is None:
            yield {0: DeltaToolCall(name="recommend_words", json_args="{}")}
            return
        for word in answer.split(" "):
            yield word + " " if not answer.endswith(word) else word

    return FunctionModel(step, stream_function=stream)
