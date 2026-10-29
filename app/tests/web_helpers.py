"""Helpers for the web tests: an app on the test databases, and a signed-in learner."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.moderation import Verdict
from juku_app.web import WebDeps, create_web_app
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import Databases
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

CSRF = re.compile(r'name="csrf" value="([^"]+)"')


class AllowAll:
    async def check(self, message: str) -> Verdict:
        assert message
        return Verdict(suggests_self_harm=False)


NOT_IN_DATA = "Maaf, tidak ada di data."


def answer_from_the_data(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(NOT_IN_DATA)])


async def stream_from_the_data(_messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str]:
    for word in NOT_IN_DATA.split(" "):
        yield word if NOT_IN_DATA.endswith(word) else word + " "


def deps(db: Databases, juku_mcp_url: str = "http://127.0.0.1:9/mcp", **overrides: Any) -> WebDeps:
    rules = load_rules()
    values: dict[str, Any] = {
        "db": db,
        "rules": rules,
        "signer": Signer(ed25519.Ed25519PrivateKey.generate(), rules),
        "session_secret": "test-session-secret-not-a-real-one",
        "model": FunctionModel(answer_from_the_data, stream_function=stream_from_the_data),
        "juku_mcp_url": juku_mcp_url,
        "shiori_gateway_key": None,
        "moderator": AllowAll(),
        "crisis_line": "TEST-LINE",
        "secure_cookies": False,
    }
    return WebDeps(**(values | overrides))


def client_for(web_deps: WebDeps) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_web_app(web_deps))
    return httpx.AsyncClient(transport=transport, base_url="http://juku.test", follow_redirects=False)


def csrf_of(page: httpx.Response) -> str:
    found = CSRF.search(page.text)
    assert found, "the form has no CSRF token"
    return found.group(1)


async def sign_up(client: httpx.AsyncClient, code: str, *, nickname: str = "Ayu", level: str = "5") -> httpx.Response:
    """The whole first visit: invite code, consent, then the learner's details."""
    page = await client.get("/masuk")
    await client.post("/masuk", data={"code": code, "csrf": csrf_of(page)})
    page = await client.get("/persetujuan")
    await client.post(
        "/persetujuan",
        data={"is_adult": "on", "accepts_service": "on", "accepts_aggregates": "on", "csrf": csrf_of(page)},
    )
    page = await client.get("/mulai")
    return await client.post(
        "/mulai",
        data={
            "nickname": nickname,
            "target_level": level,
            "timezone": "Asia/Jakarta",
            "exam_date": "",
            "csrf": csrf_of(page),
        },
    )


def found(pattern: str, page: str) -> str:
    """The first group of `pattern` in `page`; fails the test if it isn't there."""
    match = re.search(pattern, page, re.S)
    assert match, f"{pattern!r} isn't on the page"
    return match.group(1)


def csrf_header(page: httpx.Response) -> dict[str, str]:
    """The header the islands send: the token from the page's <meta name="csrf-token">."""
    return {"X-CSRF-Token": found(r'name="csrf-token" content="([^"]+)"', page.text)}
