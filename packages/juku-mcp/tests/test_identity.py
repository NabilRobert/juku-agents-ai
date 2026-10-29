"""ID2 through the server: identity comes only from the token in `_meta`, checked on every call.

The token library's own rules are tested in juku-common; these tests show
the server applies them, binds the chain to the gateway's caller stamp,
and refuses everything a token doesn't allow.
"""

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import Databases
from juku_mcp.server import build_server
from mcp import Client
from mcp_helpers import Learners, call, connected, make_deps, token_for

pytestmark = [
    pytest.mark.fitness("FF8"),
]


async def test_a_call_without_a_token_is_refused(client: Client) -> None:
    answer = await call(client, "get_progress", None)
    assert (answer.is_error, answer.body["refused"]) == (True, "no_token")


async def test_a_token_works_once(client: Client, signer: Signer, learners: Learners) -> None:
    token = token_for(signer, learners.a)
    assert not (await call(client, "get_progress", token)).is_error
    assert (await call(client, "get_progress", token)).body["refused"] == "replayed"


async def test_a_tool_outside_the_token_is_refused(client: Client, signer: Signer, learners: Learners) -> None:
    token = token_for(signer, learners.a, tools=["get_progress"])
    assert (await call(client, "recommend_words", token)).body["refused"] == "out_of_scope"


async def test_keiko_delegated_by_shiori_reads_the_same_learner(
    client: Client, signer: Signer, learners: Learners
) -> None:
    keiko = signer.delegate(token_for(signer, learners.a), to_agent="keiko", tools=["get_progress"])
    answer = await call(client, "get_progress", keiko)
    assert not answer.is_error, answer.text


async def test_an_unknown_tool_is_refused(client: Client, signer: Signer, learners: Learners) -> None:
    answer = await call(client, "delete_everything", token_for(signer, learners.a))
    assert (answer.is_error, answer.body["refused"]) == (True, "unknown_tool")


@pytest.mark.guardrail("delegation.require_gateway_caller")
async def test_behind_the_gateway_the_chain_must_match_the_calling_key(
    engine_databases: Databases, key: ed25519.Ed25519PrivateKey, signer: Signer, learners: Learners, audit_path: Path
) -> None:
    deps = make_deps(engine_databases, key, audit_path, rules=load_rules())  # require_gateway_caller: true
    async with connected(build_server(deps)) as gateway_side:
        keiko = signer.delegate(token_for(signer, learners.a), to_agent="keiko", tools=["get_progress"])
        assert (await call(gateway_side, "get_progress", keiko, caller="shiori")).body["refused"] == "actor_mismatch"
        no_stamp = token_for(signer, learners.a)
        assert (await call(gateway_side, "get_progress", no_stamp)).body["refused"] == "no_caller"
        ok = await call(gateway_side, "get_progress", token_for(signer, learners.a), caller="shiori")
        assert not ok.is_error, ok.text
