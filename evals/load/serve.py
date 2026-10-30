"""`juku serve` for the load test (FF10): the production app with a scripted Shiori, so a chat costs $0.

Mounted into the app's image by evals/load/compose.yaml. Everything but two inputs is `juku_app.cli.build_app`:
the model is a FunctionModel that calls `recommend_words` through Juku's MCP server and answers citing the
first word, so each chat still mints a delegation token, makes one real tool call and passes the citation
check; and the MCP URL points at juku-mcp directly, because the load stack has no gateway.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from juku_app.citations import NOT_IN_DATA
from juku_app.cli import admin_ids, databases, settings, signing_key
from juku_app.logs import configure_logging
from juku_app.moderation import PendingModerator
from juku_app.web import WebDeps, create_web_app
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel

JUKU_MCP_URL = os.environ.get("JUKU_LOAD_MCP_URL", "http://juku-mcp:8000/mcp")
# Longer than a learner's longest wait (2-8 s, locustfile.py). Uvicorn's default of 5 s closes connections
# Locust is about to reuse, and each such race counts as a failed request.
KEEP_ALIVE_SECONDS = 30


def cited_answer(messages: list[ModelMessage]) -> str | None:
    """The answer once `recommend_words` has returned, citing its first word; None before the tool call.

    A learner who knows every word of their level gets no words back, which is correct: like the real
    Shiori, the answer then says the data doesn't have it, the one uncited answer that counts as verified.
    """
    returns = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
    if not returns:
        return None
    returned: Any = returns[-1].content
    body = returned if isinstance(returned, dict) else json.loads(str(returned))
    words = body["words"]
    if not words:
        return NOT_IN_DATA
    return f"Pelajari kata ini dulu [ref:{words[0]['word_id']}]."


def scripted_step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    answer = cited_answer(messages)
    if answer is None:
        return ModelResponse(parts=[ToolCallPart(tool_name="recommend_words", args={})])
    return ModelResponse(parts=[TextPart(answer)])


async def scripted_stream(messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
    answer = cited_answer(messages)
    if answer is None:
        yield {0: DeltaToolCall(name="recommend_words", json_args="{}")}
        return
    yield answer


def main() -> None:
    configure_logging()
    config = settings()
    rules = load_rules()
    deps = WebDeps(
        db=databases(config, rules),
        rules=rules,
        signer=Signer(signing_key(config), rules),
        session_secret=config.session_secret,
        model=FunctionModel(scripted_step, stream_function=scripted_stream),
        juku_mcp_url=JUKU_MCP_URL,
        shiori_gateway_key=None,
        moderator=PendingModerator(),
        crisis_line=config.crisis_line,
        secure_cookies=config.secure_cookies,
        admin_public_ids=admin_ids(config),
    )
    uvicorn.run(
        create_web_app(deps),
        host="0.0.0.0",  # noqa: S104 (inside its container)
        port=8000,
        log_level="warning",
        timeout_keep_alive=KEEP_ALIVE_SECONDS,
    )


if __name__ == "__main__":
    main()
