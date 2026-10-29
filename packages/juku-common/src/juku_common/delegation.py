"""Delegation tokens (ADR-018): who an agent acts for, through whom, and for which tools.

The app mints one token per MCP tool call, signed with its Ed25519 key
(PyJWT, `EdDSA`), and the call carries it in `_meta` under META_KEY. The
claims follow OAuth 2.0 Token Exchange (RFC 8693), so a real
authorization server could issue them later without changing the checks:
- `sub`: the learner's public ID (pseudonymous);
- `act`: the chain of agents, nested, outermost = the agent acting now;
- `tools`: the tools this call may use; `purpose` and `run`;
- `aud`, `iss`, a short `exp`, and a single-use `jti`.

The one multi-hop path is learner -> Shiori -> (request_replan) -> Keiko.
A delegated token embeds its parent token, so Juku's MCP server can check
the hop only narrowed (the tools a subset, the expiry no later, the same
learner, one hop longer, on an allowed path) instead of trusting it.

Every limit comes from guardrails.yaml's `delegation` and `agents`
sections. Every refusal names a category, which the audit log and the
"refused call" alert use; the message is for people.

Rewritten from spike 6 (branch spike/delegation-chain, spikes/6-delegation-chain/delegation.py).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from juku_common.rules import Rules

META_KEY = "io.github.nabilrobert.juku/delegation"
# The gateway stamps the agent whose key made the call here, overwriting any value a client sent (P6).
CALLER_META_KEY = "io.github.nabilrobert.mcp-gateway/caller"
AGENT_PREFIX = "agent:"
ALGORITHM = "EdDSA"
REQUIRED_CLAIMS = ["iss", "aud", "sub", "iat", "exp", "jti", "act", "tools", "purpose"]


class RefusedError(Exception):
    """This token may not make this call. `category` is stable and logged; the message explains."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class Grant:
    """What a verified token allows: this learner, by this chain, these tools."""

    learner: str
    chain: tuple[str, ...]
    tools: frozenset[str]
    purpose: str
    run: str
    jti: str
    expires_at: datetime

    @property
    def agent(self) -> str:
        """The agent acting now."""
        return self.chain[0]


def chain_of(claims: Mapping[str, Any]) -> list[str]:
    """The agents in `act`, current first, without the `agent:` prefix."""
    chain: list[str] = []
    act: Any = claims.get("act")
    while isinstance(act, dict):
        actor = cast(dict[str, Any], act)
        chain.append(str(actor.get("sub", "")).removeprefix(AGENT_PREFIX))
        act = actor.get("act")
    return chain


def nest(chain: list[str]) -> dict[str, Any]:
    """RFC 8693's nested `act` claim for a chain given current first."""
    act: dict[str, Any] | None = None
    for agent in reversed(chain):
        act = {"sub": f"{AGENT_PREFIX}{agent}", **({"act": act} if act else {})}
    if act is None:
        raise ValueError("a chain needs at least one agent")
    return act


def _timestamp(now: datetime | None) -> float:
    return time.time() if now is None else now.timestamp()


class NotEd25519KeyError(ValueError):
    """A key that loads, but isn't Ed25519: the message names the setting, and how to make the right one."""


KEY_ADVICE = "make one with ops/make-secrets.sh"


def private_key_from_pem(pem: str, setting: str) -> ed25519.Ed25519PrivateKey:
    """The Ed25519 private key in `setting`. Text that isn't a key fails with cryptography's own ValueError."""
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise NotEd25519KeyError(f"{setting} isn't an Ed25519 private key: {KEY_ADVICE}")
    return key


def public_key_from_pem(pem: str, setting: str) -> ed25519.Ed25519PublicKey:
    """The Ed25519 public key in `setting`. Text that isn't a key fails with cryptography's own ValueError."""
    key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise NotEd25519KeyError(f"{setting} isn't an Ed25519 public key: {KEY_ADVICE}")
    return key


@dataclass
class Signer:
    """The app's side: mints tokens, never wider than the rule file allows the agent."""

    key: ed25519.Ed25519PrivateKey
    rules: Rules

    def _check_tools(self, agent: str, tools: list[str]) -> None:
        allowed = self.rules.tools_of(agent)
        for tool in tools:
            if tool not in allowed:
                raise ValueError(f"{agent} may not use {tool}: it isn't in guardrails.yaml's agents.{agent}")

    def mint(  # noqa: PLR0913 (keyword-only: each is one claim of the token)
        self, *, learner: str, agent: str, tools: list[str], purpose: str, run: str = "", now: datetime | None = None
    ) -> str:
        """A direct token: this agent, acting for this learner, for these tools."""
        self._check_tools(agent, tools)
        issued = _timestamp(now)
        claims = {
            "iss": self.rules.delegation.issuer,
            "aud": self.rules.delegation.audience,
            "sub": learner,
            "iat": int(issued),
            "exp": int(issued) + self.rules.delegation.token_ttl_seconds,
            "jti": uuid.uuid4().hex,
            "act": nest([agent]),
            "tools": tools,
            "purpose": purpose,
            "run": run,
        }
        return self.sign_claims(claims)

    def delegate(self, parent_token: str, *, to_agent: str, tools: list[str], now: datetime | None = None) -> str:
        """A token for the next agent: the same learner, fewer or equal tools, no later expiry, the parent inside."""
        self._check_tools(to_agent, tools)
        parent = jwt.decode(parent_token, options={"verify_signature": False})
        issued = _timestamp(now)
        claims = {
            **{name: parent[name] for name in ("iss", "aud", "sub", "purpose", "run")},
            "iat": int(issued),
            "exp": min(int(parent["exp"]), int(issued) + self.rules.delegation.token_ttl_seconds),
            "jti": uuid.uuid4().hex,
            "act": nest([to_agent, *chain_of(parent)]),
            "tools": tools,
            "parent": parent_token,
        }
        return self.sign_claims(claims)

    def sign_claims(self, claims: Mapping[str, Any]) -> str:
        """Sign claims as they are. The app uses mint and delegate; tests use this to build attacks."""
        return jwt.encode(dict(claims), self.key, algorithm=ALGORITHM)


@dataclass
class Verifier:
    """Juku's MCP server's side. Every check fails closed, with a category."""

    public_key: ed25519.Ed25519PublicKey
    rules: Rules
    # jti -> exp. One process, so in memory; at scale this moves to Postgres or Valkey.
    seen: dict[str, float] = field(default_factory=dict[str, float])

    def _decode(self, token: str, now: float) -> dict[str, Any]:
        delegation = self.rules.delegation
        try:
            claims = jwt.decode(
                token,
                self.public_key,
                algorithms=[ALGORITHM],
                audience=delegation.audience,
                issuer=delegation.issuer,
                # Time is checked below against `now`, so tests and replays can fix the clock.
                options={"require": REQUIRED_CLAIMS, "verify_exp": False, "verify_iat": False},
            )
        except jwt.InvalidAudienceError as exc:
            raise RefusedError("wrong_audience", "the token is for another service") from exc
        except jwt.InvalidIssuerError as exc:
            raise RefusedError("wrong_issuer", "the token wasn't issued by Juku's app") from exc
        except jwt.InvalidSignatureError as exc:
            raise RefusedError("bad_signature", "the token's signature doesn't verify") from exc
        except jwt.PyJWTError as exc:
            raise RefusedError("invalid_token", f"the token is malformed ({type(exc).__name__})") from exc
        if float(claims["exp"]) < now:
            raise RefusedError("expired", "the token has expired")
        return claims

    def _check_chain(self, chain: list[str]) -> None:
        if not chain or any(agent not in self.rules.agents for agent in chain):
            raise RefusedError("unknown_actor", f"the chain names an unknown agent: {chain}")
        if len(chain) > self.rules.delegation.max_agent_hops:
            raise RefusedError("too_deep", f"the chain is {len(chain)} agents deep")

    def _check_scope(self, claims: dict[str, Any], agent: str, tool: str) -> frozenset[str]:
        tools = frozenset(str(name) for name in cast(list[Any], claims["tools"]))
        if tool not in tools:
            raise RefusedError("out_of_scope", f"the token doesn't allow {tool}")
        if not tools <= self.rules.tools_of(agent):
            raise RefusedError("out_of_scope", f"the token names tools {agent} may not use")
        return tools

    def _check_hop(self, claims: dict[str, Any], chain: list[str], now: float) -> None:
        """A delegated token: on an allowed path, with its parent inside, only narrowing."""
        hop = next(
            (
                allowed
                for allowed in self.rules.delegation.allowed_delegations
                if (allowed.to_agent, allowed.from_agent) == (chain[0], chain[1])
            ),
            None,
        )
        if hop is None or len(chain) != 2:
            raise RefusedError("delegation_not_allowed", f"{' <- '.join(chain)} isn't an allowed delegation")
        parent_token = claims.get("parent")
        if not isinstance(parent_token, str):
            raise RefusedError("no_parent", "a delegated token must carry its parent")
        parent = self._decode(parent_token, now)
        if chain_of(parent) != chain[1:]:
            raise RefusedError("parent_mismatch", "the parent's chain isn't this chain's tail")
        if parent["sub"] != claims["sub"]:
            raise RefusedError("learner_changed", "the delegation switched the learner")
        if hop.via_tool not in parent["tools"]:
            raise RefusedError("parent_did_not_allow", f"the parent token didn't allow {hop.via_tool}")
        if not set(claims["tools"]) <= set(parent["tools"]):
            raise RefusedError("widened", "the delegation added tools its parent didn't have")
        if claims["exp"] > parent["exp"]:
            raise RefusedError("outlived_parent", "the delegation expires after its parent")

    def _check_caller(self, agent: str, caller: str | None) -> None:
        if caller is None:
            if self.rules.delegation.require_gateway_caller:
                raise RefusedError("no_caller", "no gateway caller stamp to bind the chain to")
            return
        if caller != agent:
            raise RefusedError("actor_mismatch", f"the chain's agent {agent} isn't the calling key's agent {caller}")

    def _check_replay(self, claims: dict[str, Any], now: float) -> None:
        self.seen = {jti: expires for jti, expires in self.seen.items() if expires >= now}
        if claims["jti"] in self.seen:
            raise RefusedError("replayed", "the token was used before; each is good for one call")
        self.seen[str(claims["jti"])] = float(claims["exp"])

    def verify(self, token: str | None, tool: str, *, caller: str | None = None, now: datetime | None = None) -> Grant:
        """The grant, if this token may call this tool now; otherwise RefusedError."""
        if not token:
            raise RefusedError("no_token", "the call carries no delegation token")
        moment = _timestamp(now)
        claims = self._decode(token, moment)
        chain = chain_of(claims)
        self._check_chain(chain)
        tools = self._check_scope(claims, chain[0], tool)
        if len(chain) > 1:
            self._check_hop(claims, chain, moment)
        elif "parent" in claims:
            raise RefusedError("unexpected_parent", "a direct token carries a parent")
        self._check_caller(chain[0], caller)
        self._check_replay(claims, moment)
        return Grant(
            learner=str(claims["sub"]),
            chain=tuple(chain),
            tools=tools,
            purpose=str(claims["purpose"]),
            run=str(claims.get("run", "")),
            jti=str(claims["jti"]),
            expires_at=datetime.fromtimestamp(float(claims["exp"]), tz=UTC),
        )
