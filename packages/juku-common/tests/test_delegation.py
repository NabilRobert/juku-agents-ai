"""ID2: delegation tokens only narrow, expire, stay single-use, and bind to the calling agent (ADR-018).

Each test names the rule it enforces. Where a rule is a number in
guardrails.yaml, a test also changes the number and shows the outcome
changes, so the rule is read from the file, not hard-coded (G1).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Grant, RefusedError, Signer, Verifier
from juku_common.rules import Rules, load_rules
from jwt.utils import base64url_decode, base64url_encode

pytestmark = pytest.mark.fitness("FF8")

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
SHIORI_TOOLS = ["get_progress", "get_memory", "request_replan"]


@pytest.fixture
def rules() -> Rules:
    return load_rules()


@pytest.fixture
def key() -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
def signer(key: ed25519.Ed25519PrivateKey, rules: Rules) -> Signer:
    return Signer(key, rules)


@pytest.fixture
def verifier(key: ed25519.Ed25519PrivateKey, rules: Rules) -> Verifier:
    """The server's verifier as the tests reach it: directly, with no gateway to stamp the caller."""
    return Verifier(key.public_key(), with_rules(rules, require_gateway_caller=False))


def with_rules(rules: Rules, **delegation: Any) -> Rules:
    return rules.model_copy(update={"delegation": rules.delegation.model_copy(update=delegation)})


def shiori_token(signer: Signer, learner: str = "lrn-a", now: datetime = NOW) -> str:
    return signer.mint(learner=learner, agent="shiori", tools=SHIORI_TOOLS, purpose="chat", now=now)


def keiko_token(signer: Signer, parent: str, tools: list[str] | None = None) -> str:
    return signer.delegate(parent, to_agent="keiko", tools=tools or ["get_progress"], now=NOW)


def refusal(verifier: Verifier, token: str | None, tool: str = "get_progress", **kwargs: Any) -> str:
    with pytest.raises(RefusedError) as caught:
        verifier.verify(token, tool, now=kwargs.pop("now", NOW), **kwargs)
    return caught.value.category


def claims_of(token: str) -> dict[str, Any]:
    return jwt.decode(token, options={"verify_signature": False})


def test_a_direct_token_grants_its_learner_chain_and_tools(signer: Signer, verifier: Verifier) -> None:
    grant = verifier.verify(shiori_token(signer), "get_progress", now=NOW)
    assert isinstance(grant, Grant)
    assert (grant.learner, grant.chain, grant.purpose) == ("lrn-a", ("shiori",), "chat")
    assert grant.tools == frozenset(SHIORI_TOOLS)


def test_no_token_is_refused(verifier: Verifier) -> None:
    assert refusal(verifier, None) == "no_token"


def test_a_token_with_its_learner_edited_is_refused(signer: Signer, verifier: Verifier) -> None:
    header, payload, signature = shiori_token(signer).split(".")
    edited = base64url_encode(base64url_decode(payload).replace(b'"lrn-a"', b'"lrn-b"')).decode()
    assert refusal(verifier, f"{header}.{edited}.{signature}") == "bad_signature"


def test_a_token_from_another_signer_is_refused(rules: Rules, verifier: Verifier) -> None:
    stranger = Signer(ed25519.Ed25519PrivateKey.generate(), rules)
    assert refusal(verifier, shiori_token(stranger)) == "bad_signature"


@pytest.mark.guardrail("delegation.token_ttl_seconds")
def test_a_token_expires_after_the_ttl(signer: Signer, verifier: Verifier, rules: Rules) -> None:
    token = shiori_token(signer)
    ttl = timedelta(seconds=rules.delegation.token_ttl_seconds)
    assert verifier.verify(token, "get_progress", now=NOW + ttl - timedelta(seconds=1))
    assert refusal(verifier, shiori_token(signer), now=NOW + ttl + timedelta(seconds=1)) == "expired"


@pytest.mark.guardrail("delegation.token_ttl_seconds")
def test_the_ttl_comes_from_the_rule_file(key: ed25519.Ed25519PrivateKey, rules: Rules) -> None:
    short = Signer(key, with_rules(rules, token_ttl_seconds=5))
    claims = claims_of(short.mint(learner="lrn-a", agent="shiori", tools=SHIORI_TOOLS, purpose="chat", now=NOW))
    assert claims["exp"] - claims["iat"] == 5


@pytest.mark.guardrail("delegation.audience")
def test_a_token_for_another_audience_is_refused(signer: Signer, verifier: Verifier) -> None:
    claims = claims_of(shiori_token(signer)) | {"aud": "mcp-backbone"}
    assert refusal(verifier, signer.sign_claims(claims)) == "wrong_audience"


@pytest.mark.guardrail("delegation.issuer")
def test_a_token_from_another_issuer_is_refused(signer: Signer, verifier: Verifier) -> None:
    claims = claims_of(shiori_token(signer)) | {"iss": "someone-else"}
    assert refusal(verifier, signer.sign_claims(claims)) == "wrong_issuer"


def test_a_token_is_single_use(signer: Signer, verifier: Verifier) -> None:
    token = shiori_token(signer)
    verifier.verify(token, "get_progress", now=NOW)
    assert refusal(verifier, token) == "replayed"


def test_a_tool_the_token_does_not_name_is_refused(signer: Signer, verifier: Verifier) -> None:
    assert refusal(verifier, shiori_token(signer), "recommend_words") == "out_of_scope"


@pytest.mark.guardrail("agents")
def test_a_token_naming_a_tool_outside_the_agents_list_is_refused(signer: Signer, verifier: Verifier) -> None:
    claims = claims_of(shiori_token(signer)) | {"act": {"sub": "agent:nikki"}, "tools": ["get_progress"]}
    assert refusal(verifier, signer.sign_claims(claims)) == "out_of_scope"


@pytest.mark.guardrail("agents")
def test_the_app_will_not_mint_a_tool_outside_the_agents_list(signer: Signer) -> None:
    with pytest.raises(ValueError, match="nikki may not use get_progress"):
        signer.mint(learner="lrn-a", agent="nikki", tools=["get_progress"], purpose="weekly_run", now=NOW)


def test_an_unknown_agent_in_the_chain_is_refused(signer: Signer, verifier: Verifier) -> None:
    claims = claims_of(shiori_token(signer)) | {"act": {"sub": "agent:mallory"}}
    assert refusal(verifier, signer.sign_claims(claims)) == "unknown_actor"


def test_shiori_can_hand_keiko_a_narrower_token(signer: Signer, verifier: Verifier) -> None:
    grant = verifier.verify(keiko_token(signer, shiori_token(signer)), "get_progress", now=NOW)
    assert (grant.learner, grant.chain, grant.tools) == ("lrn-a", ("keiko", "shiori"), frozenset({"get_progress"}))


def test_a_delegated_token_never_outlives_its_parent(signer: Signer) -> None:
    parent = shiori_token(signer, now=NOW - timedelta(seconds=30))
    child = claims_of(signer.delegate(parent, to_agent="keiko", tools=["get_progress"], now=NOW))
    assert child["exp"] == claims_of(parent)["exp"]


@pytest.mark.guardrail("delegation.allowed_delegations")
def test_a_hop_that_adds_a_tool_is_refused(signer: Signer, verifier: Verifier) -> None:
    child = claims_of(keiko_token(signer, shiori_token(signer))) | {"tools": ["get_progress", "recommend_words"]}
    assert refusal(verifier, signer.sign_claims(child)) == "widened"


def test_a_hop_that_outlives_its_parent_is_refused(signer: Signer, verifier: Verifier) -> None:
    child = claims_of(keiko_token(signer, shiori_token(signer)))
    assert refusal(verifier, signer.sign_claims(child | {"exp": child["exp"] + 600})) == "outlived_parent"


def test_a_hop_that_switches_the_learner_is_refused(signer: Signer, verifier: Verifier) -> None:
    child = claims_of(keiko_token(signer, shiori_token(signer)))
    assert refusal(verifier, signer.sign_claims(child | {"sub": "lrn-b"})) == "learner_changed"


@pytest.mark.guardrail("delegation.max_agent_hops")
def test_a_chain_three_agents_deep_is_refused(signer: Signer, verifier: Verifier) -> None:
    child = claims_of(keiko_token(signer, shiori_token(signer)))
    deeper = child | {"act": {"sub": "agent:keiko", "act": {"sub": "agent:keiko", "act": {"sub": "agent:shiori"}}}}
    assert refusal(verifier, signer.sign_claims(deeper)) == "too_deep"


@pytest.mark.guardrail("delegation.max_agent_hops")
def test_the_hop_limit_comes_from_the_rule_file(key: ed25519.Ed25519PrivateKey, rules: Rules, signer: Signer) -> None:
    strict = Verifier(key.public_key(), with_rules(rules, max_agent_hops=1))
    assert refusal(strict, keiko_token(signer, shiori_token(signer))) == "too_deep"


@pytest.mark.guardrail("delegation.allowed_delegations")
def test_a_hop_not_on_the_allowed_path_is_refused(signer: Signer, verifier: Verifier) -> None:
    child = claims_of(keiko_token(signer, shiori_token(signer)))
    reversed_chain = child | {"act": {"sub": "agent:shiori", "act": {"sub": "agent:keiko"}}}
    assert refusal(verifier, signer.sign_claims(reversed_chain)) == "delegation_not_allowed"


@pytest.mark.guardrail("delegation.allowed_delegations")
def test_without_the_allowed_path_keiko_cannot_be_delegated_to(
    key: ed25519.Ed25519PrivateKey, rules: Rules, signer: Signer
) -> None:
    closed = Verifier(key.public_key(), with_rules(rules, allowed_delegations=[]))
    assert refusal(closed, keiko_token(signer, shiori_token(signer))) == "delegation_not_allowed"


def test_a_delegated_token_without_its_parent_is_refused(signer: Signer, verifier: Verifier) -> None:
    child = claims_of(keiko_token(signer, shiori_token(signer)))
    del child["parent"]
    assert refusal(verifier, signer.sign_claims(child)) == "no_parent"


def test_a_parent_that_did_not_allow_the_handover_is_refused(signer: Signer, verifier: Verifier) -> None:
    parent = signer.mint(learner="lrn-a", agent="shiori", tools=["get_progress"], purpose="chat", now=NOW)
    child = claims_of(keiko_token(signer, shiori_token(signer))) | {"parent": parent}
    assert refusal(verifier, signer.sign_claims(child)) == "parent_did_not_allow"


def test_a_direct_token_carrying_a_parent_is_refused(signer: Signer, verifier: Verifier) -> None:
    claims = claims_of(shiori_token(signer)) | {"parent": shiori_token(signer)}
    assert refusal(verifier, signer.sign_claims(claims)) == "unexpected_parent"


@pytest.mark.guardrail("delegation.require_gateway_caller")
def test_the_chains_agent_must_be_the_calling_key(signer: Signer, verifier: Verifier) -> None:
    keiko = keiko_token(signer, shiori_token(signer))
    assert refusal(verifier, keiko, caller="shiori") == "actor_mismatch"
    assert verifier.verify(keiko_token(signer, shiori_token(signer)), "get_progress", caller="keiko", now=NOW)


@pytest.mark.guardrail("delegation.require_gateway_caller")
def test_the_caller_rule_comes_from_the_rule_file(key: ed25519.Ed25519PrivateKey, rules: Rules, signer: Signer) -> None:
    behind_gateway = Verifier(key.public_key(), with_rules(rules, require_gateway_caller=True))
    assert refusal(behind_gateway, shiori_token(signer)) == "no_caller"
    direct = Verifier(key.public_key(), with_rules(rules, require_gateway_caller=False))
    assert direct.verify(shiori_token(signer), "get_progress", now=NOW)


@pytest.mark.parametrize("token", ["not-a-token", "a.b.c"])
def test_a_malformed_token_is_refused(verifier: Verifier, token: str) -> None:
    assert refusal(verifier, token) == "invalid_token"


def test_a_token_missing_a_required_claim_is_refused(signer: Signer, verifier: Verifier) -> None:
    claims = claims_of(shiori_token(signer))
    del claims["jti"]
    assert refusal(verifier, signer.sign_claims(claims)) == "invalid_token"


def test_a_parent_whose_chain_is_not_the_hops_tail_is_refused(signer: Signer, verifier: Verifier) -> None:
    parent = signer.sign_claims(claims_of(shiori_token(signer)) | {"act": {"sub": "agent:keiko"}})
    child = claims_of(keiko_token(signer, shiori_token(signer))) | {"parent": parent}
    assert refusal(verifier, signer.sign_claims(child)) == "parent_mismatch"
