"""Spike 6: a tiny Juku MCP server that takes its identity only from the
delegation token in each request's `_meta` (ADR-006, ADR-018).

No tool takes a learner ID, or any argument. Every call, allowed or refused,
is logged with its chain. Each result reports a hash of the token it
received and the `_meta` keys it saw, so a client can tell whether `_meta`
arrived unchanged.

Usage: python juku_server.py <port> <public key PEM> <audit log> [--require-caller]
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from typing import Any

import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from mcp.server import Server, ServerRequestContext
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, PaginatedRequestParams, TextContent, Tool

from delegation import CALLER_META_KEY, META_KEY, Refused, Verifier, chain_of

# Two learners' rows. The point is which ones a call can reach, not the data.
ROWS: dict[str, dict[str, Any]] = {
    "lrn_a": {"progress": {"n5_words_known": 312}, "memory": ["sering tertukar は dan が"]},
    "lrn_b": {"progress": {"n5_words_known": 45}, "memory": ["belajar malam hari"]},
}
NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}
TOOLS = [
    Tool(name="get_progress", description="The learner's progress.", input_schema=NO_ARGS),
    Tool(name="get_memory", description="What Shiori remembers about the learner.", input_schema=NO_ARGS),
    Tool(name="request_replan", description="Ask Keiko for a new weekly plan.", input_schema=NO_ARGS),
]


def build(verifier: Verifier, log_path: str, require_caller: bool) -> Server:
    log = open(log_path, "a", buffering=1, encoding="utf-8")  # noqa: SIM115 (lives as long as the server)

    async def list_tools(_: ServerRequestContext[Any], __: PaginatedRequestParams | None) -> ListToolsResult:
        return ListToolsResult(tools=TOOLS)

    async def call_tool(_: ServerRequestContext[Any], params: CallToolRequestParams) -> CallToolResult:
        meta: dict[str, Any] = dict(params.meta or {})
        token = meta.get(META_KEY)
        caller = meta.get(CALLER_META_KEY)
        seen = {
            "received_token_sha256": hashlib.sha256(token.encode()).hexdigest() if isinstance(token, str) else None,
            "received_meta_keys": sorted(meta),
            "received_traceparent": meta.get("traceparent"),
        }
        record: dict[str, Any] = {"at": time.time(), "tool": params.name, "caller": caller, **seen}
        try:
            if params.arguments:
                raise Refused(f"unexpected arguments {sorted(params.arguments)}: identity comes from the token")
            if params.name not in {t.name for t in TOOLS}:
                raise Refused(f"unknown tool {params.name!r}")
            claims = verifier.verify(
                token if isinstance(token, str) else None,
                params.name,
                caller=caller if isinstance(caller, str) else None,
                require_caller=require_caller,
            )
        except Refused as exc:
            log.write(json.dumps({**record, "decision": "refused", "reason": str(exc)}) + "\n")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Refused: {exc}")],
                structured_content={"refused": str(exc), **seen},
                is_error=True,
            )
        learner = claims["sub"]
        record.update(
            decision="allowed", learner=learner, chain=chain_of(claims), jti=claims["jti"], purpose=claims["purpose"]
        )
        log.write(json.dumps(record) + "\n")
        if params.name == "request_replan":
            data: Any = {"queued": True}
        else:
            data = ROWS.get(learner, {}).get(params.name.removeprefix("get_"))
        body = {"learner": learner, "data": data, **seen}
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(body, ensure_ascii=False))], structured_content=body
        )

    return Server("juku-spike6", on_list_tools=list_tools, on_call_tool=call_tool)


def main() -> None:
    port, pem, log_path = int(sys.argv[1]), sys.argv[2], sys.argv[3]
    public = serialization.load_pem_public_key(open(pem, "rb").read())
    assert isinstance(public, ec.EllipticCurvePublicKey)
    server = build(Verifier(public), log_path, require_caller="--require-caller" in sys.argv)
    app = server.streamable_http_app(streamable_http_path="/mcp")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
