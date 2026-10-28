"""Spike 6: can a PydanticAI agent put the delegation token in each tool
call's `_meta`, and does it reach Juku's MCP server unchanged through the
gateway?

No hand-written loop: a PydanticAI `Agent` with its `MCPToolset` (Streamable
HTTP, with the agent's gateway key), and a `process_tool_call` hook that
mints a fresh single-use token for each call and passes it as the call's
`metadata`, which PydanticAI sends as the request's `_meta`. The models are
PydanticAI's `TestModel` and `FunctionModel`, so it costs $0.

Usage: python pai_check.py <mode> <url> <app private key PEM> <keys JSON>
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from delegation import META_KEY, Signer

TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
CHAT = ["get_progress", "get_memory", "request_replan"]


@dataclass
class Delegation:
    """What the app knows about this run: who it acts for, and through whom."""

    signer: Signer
    learner: str
    chain: list[str]
    tools: list[str]
    parent: str | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)


async def with_token(ctx: RunContext[Delegation], call_tool: CallToolFunc, name: str, args: dict[str, Any]) -> Any:
    """PydanticAI's hook around every MCP tool call: mint a token for this
    one call and send it in `_meta`."""
    d = ctx.deps
    token = d.signer.mint(d.learner, d.chain, d.tools, purpose="weekly_run" if d.parent else "chat", parent=d.parent)
    result = await call_tool(name, args, metadata={META_KEY: token, "traceparent": TRACEPARENT})
    body = result if isinstance(result, dict) else json.loads(result) if isinstance(result, str) else {}
    d.calls.append(
        {
            "tool": name,
            "allowed": "refused" not in body,
            "learner_returned": body.get("learner"),
            "refused": body.get("refused"),
            "token_arrived_unchanged": body.get("received_token_sha256") == hashlib.sha256(token.encode()).hexdigest(),
            "traceparent_arrived_unchanged": body.get("received_traceparent") == TRACEPARENT,
        }
    )
    return result


def keiko_model() -> FunctionModel:
    """Keiko, scripted: read progress, then memory, then answer."""

    def step(messages: list[ModelMessage], _: AgentInfo) -> ModelResponse:
        done = sum(1 for m in messages if isinstance(m, ModelResponse) for p in m.parts if isinstance(p, ToolCallPart))
        plan = ["get_progress", "get_memory"]
        if done < len(plan):
            return ModelResponse(parts=[ToolCallPart(tool_name=plan[done], args={})])
        return ModelResponse(parts=[TextPart("Rencana minggu ini siap.")])

    return FunctionModel(step)


async def run(url: str, key: str, model: Any, deps: Delegation) -> dict[str, Any]:
    toolset = MCPToolset(
        url, headers={"Authorization": f"Bearer {key}"}, process_tool_call=with_token, tool_error_behavior="error"
    )
    agent = Agent(model, deps_type=Delegation, toolsets=[toolset])
    try:
        result = await agent.run("Bagaimana kemajuanku?", deps=deps)
        output: str | None = str(result.output)
    except Exception as exc:  # a refusal raised as a tool error still ends the run; record it
        output = f"{type(exc).__name__}: {str(exc)[:160]}"
    return {"output": output, "calls": deps.calls}


def main() -> None:
    mode, url, pem, keys_path = sys.argv[1:5]
    private = serialization.load_pem_private_key(Path(pem).read_bytes(), password=None)
    assert isinstance(private, ed25519.Ed25519PrivateKey)
    app = Signer(private)
    keys = json.loads(Path(keys_path).read_text())
    # Shiori's run (TestModel calls get_progress once), then Keiko's, delegated
    # through Shiori's request_replan (FunctionModel calls two tools).
    shiori = asyncio.run(
        run(
            url,
            keys["shiori"],
            TestModel(call_tools=["get_progress"]),
            Delegation(app, "lrn_a", ["agent:shiori"], CHAT),
        )
    )
    parent = app.mint("lrn_a", ["agent:shiori"], CHAT)
    keiko = asyncio.run(
        run(
            url,
            keys["keiko"],
            keiko_model(),
            Delegation(app, "lrn_a", ["agent:keiko", "agent:shiori"], ["get_progress", "get_memory"], parent=parent),
        )
    )
    print(
        json.dumps(
            {"mode": mode, "shiori (TestModel)": shiori, "keiko (FunctionModel)": keiko}, ensure_ascii=False, indent=1
        )
    )


if __name__ == "__main__":
    main()
