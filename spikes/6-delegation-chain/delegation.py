"""Spike 6: delegation tokens (ADR-018), minted by the app, checked by Juku's
MCP server.

A token is an ES256 JWT with claims shaped on OAuth 2.0 Token Exchange
(RFC 8693): the learner as `sub`, the agents as a nested `act` (outermost =
the agent acting now), the purpose and run, the allowed `tools`, the
audience and a short expiry. It is single-use (`jti`): the app mints one per
tool call, which fits MCP 2026-07-28, where every request stands alone.

The one multi-hop path is learner -> Shiori -> (request_replan) -> Keiko. A
delegated token carries its parent token, so the server can check that the
hop only narrowed: a subset of the tools, an expiry no later, the same
learner, and a chain exactly one hop longer.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

ISSUER = "juku-app"
AUDIENCE = "juku-mcp"
META_KEY = "io.github.nabilrobert.juku/delegation"
CALLER_META_KEY = "io.github.nabilrobert.mcp-gateway/caller"
AGENTS = frozenset({"agent:shiori", "agent:keiko", "agent:nikki", "agent:tadashi"})
MAX_AGENT_HOPS = 2
# The only delegation ADR-018 allows: Shiori hands Keiko a replan.
DELEGATIONS = {("agent:keiko", "agent:shiori"): "request_replan"}
REQUIRED = ["iss", "aud", "sub", "iat", "exp", "jti", "act", "tools", "purpose"]


class Refused(Exception):
    """A token or call that must not run. The message is the logged reason."""


def chain_of(claims: dict[str, Any]) -> list[str]:
    """The actors, current first: act.sub, then act.act.sub, and so on."""
    chain: list[str] = []
    act = claims.get("act")
    while isinstance(act, dict):
        chain.append(str(act.get("sub")))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
        act = act.get("act")  # pyright: ignore[reportUnknownMemberType]
    return chain


def nest(chain: list[str]) -> dict[str, Any]:
    act: dict[str, Any] | None = None
    for agent in reversed(chain):
        act = {"sub": agent, **({"act": act} if act else {})}
    assert act is not None
    return act


@dataclass
class Signer:
    """The app's signer. In the spike its key is made fresh at start-up."""

    key: ec.EllipticCurvePrivateKey = field(default_factory=lambda: ec.generate_private_key(ec.SECP256R1()))

    def public(self) -> ec.EllipticCurvePublicKey:
        return self.key.public_key()

    def mint(
        self,
        learner: str,
        chain: list[str],
        tools: list[str],
        *,
        purpose: str = "chat",
        run: str = "",
        ttl_s: int = 60,
        parent: str | None = None,
        audience: str = AUDIENCE,
        now: float | None = None,
        exp: float | None = None,
    ) -> str:
        t = time.time() if now is None else now
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": audience,
            "sub": learner,
            "iat": int(t),
            "exp": int(exp if exp is not None else t + ttl_s),
            "jti": uuid.uuid4().hex,
            "act": nest(chain),
            "tools": tools,
            "purpose": purpose,
            "run": run,
        }
        if parent is not None:
            claims["parent"] = parent
        return jwt.encode(claims, self.key, algorithm="ES256")


@dataclass
class Verifier:
    """Juku's MCP server side. Every check fails closed."""

    public_key: ec.EllipticCurvePublicKey
    seen: dict[str, float] = field(default_factory=dict)  # jti -> exp, for replay

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self.public_key,
                algorithms=["ES256"],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={"require": REQUIRED},
                leeway=0,
            )
        except jwt.ExpiredSignatureError as exc:
            raise Refused("expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise Refused("wrong audience") from exc
        except jwt.InvalidSignatureError as exc:
            raise Refused("bad signature") from exc
        except jwt.PyJWTError as exc:
            raise Refused(f"invalid token: {type(exc).__name__}") from exc

    def verify(
        self,
        token: str | None,
        tool: str,
        *,
        caller: str | None = None,
        require_caller: bool = False,
        now: float | None = None,
    ) -> dict[str, Any]:
        """The claims, if this token may make this call; otherwise Refused."""
        if not token:
            raise Refused("no delegation token")
        claims = self._decode(token)
        chain = chain_of(claims)
        if not chain or any(agent not in AGENTS for agent in chain):
            raise Refused("unknown actor in chain")
        if len(chain) > MAX_AGENT_HOPS:
            raise Refused(f"chain too deep: {len(chain)} agent hops")
        if tool not in claims["tools"]:
            raise Refused(f"tool {tool!r} not in the token's scope")
        if len(chain) > 1:
            self._check_hop(claims, chain)
        elif "parent" in claims:
            raise Refused("a parent token on a direct chain")
        if require_caller and caller is None:
            raise Refused("no gateway caller to bind the chain to")
        if caller is not None and f"agent:{caller}" != chain[0]:
            raise Refused(f"chain's actor {chain[0]} is not the calling key's agent {caller}")
        t = time.time() if now is None else now
        self.seen = {j: e for j, e in self.seen.items() if e >= t}
        if claims["jti"] in self.seen:
            raise Refused("replayed token")
        self.seen[claims["jti"]] = claims["exp"]
        return claims

    def _check_hop(self, claims: dict[str, Any], chain: list[str]) -> None:
        tool_for_hop = DELEGATIONS.get((chain[0], chain[1]))
        if tool_for_hop is None or len(chain) != 2:
            raise Refused(f"delegation {' <- '.join(chain)} is not allowed")
        parent_token = claims.get("parent")
        if not isinstance(parent_token, str):
            raise Refused("delegated token without its parent")
        parent = self._decode(parent_token)
        if chain_of(parent) != chain[1:]:
            raise Refused("parent's chain doesn't match")
        if parent["sub"] != claims["sub"]:
            raise Refused("delegation changed the learner")
        if tool_for_hop not in parent["tools"]:
            raise Refused(f"parent token didn't allow {tool_for_hop}")
        if not set(claims["tools"]) <= set(parent["tools"]):
            raise Refused("delegation widened the tools")
        if claims["exp"] > parent["exp"]:
            raise Refused("delegation extended the expiry")
