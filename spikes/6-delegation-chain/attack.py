"""Spike 6: try to break the delegation chain, directly or through a gateway.

Every attempt is a real MCP call with its token in `_meta`. For each one it
records: whether it was allowed, who refused it and why, whether the token
and a `traceparent` arrived unchanged, and whether a log line was written
(the Juku server's log, or the gateway's audit log).

Usage: python attack.py <mode> <url> <app private key PEM> <juku log> [<gateway log> <keys JSON>]
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from delegation import CALLER_META_KEY, META_KEY, Signer

A, B = "lrn_a", "lrn_b"
SHIORI, KEIKO, NIKKI = "agent:shiori", "agent:keiko", "agent:nikki"
CHAT = ["get_progress", "get_memory", "request_replan"]
# name, attack?, agent key, tool, token, extra _meta, arguments
Attempt = tuple[str, bool, str | None, str, Callable[[], str | None], dict[str, Any], dict[str, Any]]
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"


def lines(path: str | None) -> int:
    return len(Path(path).read_text().splitlines()) if path and Path(path).exists() else 0


async def call(url: str, key: str | None, tool: str, meta: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with (
        httpx2.AsyncClient(headers=headers, timeout=30.0) as http,
        Client(streamable_http_client(url, http_client=http)) as client,
    ):
        result = await client.call_tool(tool, args or None, meta=meta)  # pyright: ignore[reportArgumentType]
    text = "\n".join(getattr(c, "text", "") for c in result.content)  # pyright: ignore[reportAttributeAccessIssue]
    structured = getattr(result, "structured_content", None) or {}
    return {"is_error": bool(getattr(result, "is_error", False)), "text": text, "structured": structured}


def main() -> None:
    mode, url, pem, juku_log = sys.argv[1:5]
    gw_log = sys.argv[5] if len(sys.argv) > 5 else None
    keys: dict[str, str] = json.loads(Path(sys.argv[6]).read_text()) if len(sys.argv) > 6 else {}
    private = serialization.load_pem_private_key(Path(pem).read_bytes(), password=None)
    assert isinstance(private, ec.EllipticCurvePrivateKey)
    app = Signer(private)
    shiori, keiko = keys.get("shiori"), keys.get("keiko")

    def keiko_token(
        tools: list[str] | None = None, learner: str = A, extend: int = 0, parent_tools: list[str] | None = None
    ) -> str:
        now = time.time()
        parent = app.mint(A, [SHIORI], parent_tools or CHAT, exp=now + 60)
        return app.mint(
            learner,
            [KEIKO, SHIORI],
            tools or ["get_progress"],
            purpose="weekly_run",
            run="run-1",
            parent=parent,
            exp=now + 60 + extend,
        )

    def edited_token() -> str:
        head, _, sig = app.mint(A, [SHIORI], CHAT).split(".")
        body = jwt.decode(app.mint(B, [SHIORI], CHAT), options={"verify_signature": False})
        return f"{head}.{base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b'=').decode()}.{sig}"

    replay = app.mint(A, [SHIORI], CHAT)
    attempts: list[Attempt] = [
        (
            "Shiori reads her learner's progress",
            False,
            shiori,
            "get_progress",
            lambda: app.mint(A, [SHIORI], CHAT),
            {},
            {},
        ),
        ("Keiko, delegated by Shiori, reads progress", False, keiko, "get_progress", keiko_token, {}, {}),
        ("Replay, first use", False, shiori, "get_progress", lambda: replay, {}, {}),
        (
            "Another learner: a learner_id argument",
            True,
            shiori,
            "get_progress",
            lambda: app.mint(A, [SHIORI], CHAT),
            {},
            {"learner_id": B},
        ),
        (
            "Another learner: a token for B from another signer",
            True,
            shiori,
            "get_progress",
            lambda: Signer().mint(B, [SHIORI], CHAT),
            {},
            {},
        ),
        ("Another learner: A's token with its learner edited to B", True, shiori, "get_progress", edited_token, {}, {}),
        (
            "Another learner: Keiko's hop switches to B",
            True,
            keiko,
            "get_progress",
            lambda: keiko_token(learner=B),
            {},
            {},
        ),
        (
            "Widened scope: a tool outside the token",
            True,
            shiori,
            "get_memory",
            lambda: app.mint(A, [SHIORI], ["get_progress"]),
            {},
            {},
        ),
        (
            "Widened scope: Keiko's hop adds a tool",
            True,
            keiko,
            "get_progress",
            lambda: keiko_token(tools=["get_progress", "get_memory"], parent_tools=["get_progress", "request_replan"]),
            {},
            {},
        ),
        (
            "Widened scope: Keiko's hop outlives its parent",
            True,
            keiko,
            "get_progress",
            lambda: keiko_token(extend=30),
            {},
            {},
        ),
        (
            "Expired token",
            True,
            shiori,
            "get_progress",
            lambda: app.mint(A, [SHIORI], CHAT, exp=time.time() - 1),
            {},
            {},
        ),
        ("Replayed token", True, shiori, "get_progress", lambda: replay, {}, {}),
        (
            "Wrong audience (MCP-backbone's)",
            True,
            shiori,
            "get_progress",
            lambda: app.mint(A, [SHIORI], CHAT, audience="mcp-backbone"),
            {},
            {},
        ),
        (
            "A chain 3 agent hops deep",
            True,
            keiko,
            "get_progress",
            lambda: app.mint(A, [NIKKI, KEIKO, SHIORI], CHAT),
            {},
            {},
        ),
        (
            "Keiko's key carrying Shiori's chain",
            True,
            keiko,
            "get_progress",
            lambda: app.mint(A, [SHIORI], CHAT),
            {},
            {},
        ),
        (
            "Keiko's key, Shiori's chain, and a forged caller in _meta",
            True,
            keiko,
            "get_progress",
            lambda: app.mint(A, [SHIORI], CHAT),
            {CALLER_META_KEY: "shiori"},
            {},
        ),
        (
            "Keiko calls a tool outside her gateway allow-list",
            True,
            keiko,
            "request_replan",
            lambda: app.mint(A, [KEIKO], CHAT),
            {},
            {},
        ),
        ("No token at all", True, shiori, "get_progress", lambda: None, {}, {}),
    ]

    results: list[dict[str, Any]] = []
    for name, is_attack, key, tool, make, extra, args in attempts:
        token = make()
        meta: dict[str, Any] = {"traceparent": TRACEPARENT, **extra}
        if token is not None:
            meta[META_KEY] = token
        before = (lines(juku_log), lines(gw_log))
        try:
            out = asyncio.run(call(url, key, tool, meta, args))
        except Exception as exc:  # a refusal at the transport (e.g. a 401) is still a refusal
            out = {"is_error": True, "text": f"{type(exc).__name__}: {exc}", "structured": {}}
        after = (lines(juku_log), lines(gw_log))
        s = out["structured"]
        sent = hashlib.sha256(token.encode()).hexdigest() if token else None
        allowed = not out["is_error"]
        if allowed:
            by = "-"
        elif out["text"].startswith("Refused:"):
            by = "Juku server"
        elif "gateway" in out["text"].lower():
            by = "gateway"
        else:
            by = "transport"
        results.append(
            {
                "attempt": name,
                "attack": is_attack,
                "tool": tool,
                "allowed": allowed,
                "refused_by": by,
                "reason": out["text"][:160] if not allowed else "",
                "learner_returned": s.get("learner"),
                "token_arrived_unchanged": (s.get("received_token_sha256") == sent) if sent else None,
                "traceparent_arrived_unchanged": (s.get("received_traceparent") == TRACEPARENT) if s else None,
                "traceparent_received": s.get("received_traceparent") if s else None,
                "juku_log_lines": after[0] - before[0],
                "gateway_log_lines": after[1] - before[1],
            }
        )

    attacks = [r for r in results if r["attack"]]
    legit = [r for r in results if not r["attack"]]
    report = {
        "mode": mode,
        "legit_allowed": sum(r["allowed"] for r in legit),
        "legit": len(legit),
        "attacks_refused": sum(not r["allowed"] for r in attacks),
        "attacks": len(attacks),
        "attacks_logged": sum((r["juku_log_lines"] + r["gateway_log_lines"]) > 0 for r in attacks),
        "results": results,
    }
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
