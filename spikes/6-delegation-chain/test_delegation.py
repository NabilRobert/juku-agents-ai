"""Each rule of ADR-018, one test each. Mutation-checked: removing any check
in delegation.py makes at least one of these fail (see README)."""

import base64
import json
import time

import jwt
import pytest

from delegation import Refused, Signer, Verifier

A, B = "lrn_a", "lrn_b"
SHIORI, KEIKO, NIKKI = "agent:shiori", "agent:keiko", "agent:nikki"
CHAT_TOOLS = ["get_progress", "get_memory", "request_replan"]


@pytest.fixture
def app() -> Signer:
    return Signer()


@pytest.fixture
def server(app: Signer) -> Verifier:
    return Verifier(app.public())


def keiko_token(
    app: Signer,
    *,
    tools: list[str] | None = None,
    learner: str = A,
    extend: int = 0,
    parent_tools: list[str] | None = None,
) -> str:
    now = time.time()
    parent = app.mint(A, [SHIORI], parent_tools or CHAT_TOOLS, exp=now + 60)
    return app.mint(
        learner, [KEIKO, SHIORI], tools or ["get_progress"], purpose="weekly_run", parent=parent, exp=now + 60 + extend
    )


def refused(server: Verifier, token: str | None, tool: str, reason: str, **kw: object) -> None:
    with pytest.raises(Refused, match=reason):
        server.verify(token, tool, **kw)  # pyright: ignore[reportArgumentType]


def test_a_direct_call_in_scope_passes(app: Signer, server: Verifier) -> None:
    claims = server.verify(app.mint(A, [SHIORI], CHAT_TOOLS), "get_progress")
    assert claims["sub"] == A


def test_a_narrowed_delegation_passes(app: Signer, server: Verifier) -> None:
    assert server.verify(keiko_token(app), "get_progress")["sub"] == A


def test_no_token(server: Verifier) -> None:
    refused(server, None, "get_progress", "no delegation token")


def test_another_signer(server: Verifier) -> None:
    refused(server, Signer().mint(B, [SHIORI], CHAT_TOOLS), "get_progress", "bad signature")


def test_edited_learner(app: Signer, server: Verifier) -> None:
    head, body, sig = app.mint(A, [SHIORI], CHAT_TOOLS).split(".")
    claims = jwt.decode(app.mint(B, [SHIORI], CHAT_TOOLS), options={"verify_signature": False})
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    refused(server, f"{head}.{forged}.{sig}", "get_progress", "bad signature")
    assert body  # the original body was replaced


def test_unsigned_token(server: Verifier) -> None:
    token = jwt.encode({"sub": A}, key="", algorithm="none")
    refused(server, token, "get_progress", "invalid token")


def test_tool_outside_scope(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [SHIORI], ["get_progress"]), "get_memory", "not in the token's scope")


def test_expired(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [SHIORI], CHAT_TOOLS, exp=time.time() - 1), "get_progress", "expired")


def test_replayed(app: Signer, server: Verifier) -> None:
    token = app.mint(A, [SHIORI], CHAT_TOOLS)
    server.verify(token, "get_progress")
    refused(server, token, "get_progress", "replayed")


def test_wrong_audience(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [SHIORI], CHAT_TOOLS, audience="mcp-backbone"), "get_progress", "wrong audience")


def test_three_hops(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [NIKKI, KEIKO, SHIORI], CHAT_TOOLS), "get_progress", "too deep")


def test_unknown_agent(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, ["agent:mallory"], CHAT_TOOLS), "get_progress", "unknown actor")


def test_delegation_not_on_the_allowed_path(app: Signer, server: Verifier) -> None:
    parent = app.mint(A, [KEIKO], CHAT_TOOLS)
    refused(server, app.mint(A, [SHIORI, KEIKO], ["get_progress"], parent=parent), "get_progress", "not allowed")


def test_delegation_without_parent(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [KEIKO, SHIORI], ["get_progress"]), "get_progress", "without its parent")


def test_parent_on_a_direct_chain(app: Signer, server: Verifier) -> None:
    parent = app.mint(A, [SHIORI], CHAT_TOOLS)
    refused(server, app.mint(A, [SHIORI], CHAT_TOOLS, parent=parent), "get_progress", "parent token on a direct")


def test_delegation_widens_tools(app: Signer, server: Verifier) -> None:
    token = keiko_token(app, tools=["get_progress", "get_memory"], parent_tools=["get_progress", "request_replan"])
    refused(server, token, "get_progress", "widened the tools")


def test_delegation_extends_expiry(app: Signer, server: Verifier) -> None:
    refused(server, keiko_token(app, extend=30), "get_progress", "extended the expiry")


def test_delegation_changes_learner(app: Signer, server: Verifier) -> None:
    refused(server, keiko_token(app, learner=B), "get_progress", "changed the learner")


def test_parent_without_replan(app: Signer, server: Verifier) -> None:
    refused(server, keiko_token(app, parent_tools=["get_progress"]), "get_progress", "didn't allow request_replan")


def test_parent_chain_mismatch(app: Signer, server: Verifier) -> None:
    parent = app.mint(A, [NIKKI], CHAT_TOOLS)
    token = app.mint(A, [KEIKO, SHIORI], ["get_progress"], parent=parent)
    refused(server, token, "get_progress", "parent's chain")


def test_wrong_agent_key(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [SHIORI], CHAT_TOOLS), "get_progress", "not the calling key's agent", caller="keiko")


def test_caller_required_but_missing(app: Signer, server: Verifier) -> None:
    refused(server, app.mint(A, [SHIORI], CHAT_TOOLS), "get_progress", "no gateway caller", require_caller=True)
