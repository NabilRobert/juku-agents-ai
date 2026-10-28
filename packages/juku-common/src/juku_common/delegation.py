"""Delegation tokens (ADR-018) (stub: lands in the next commit)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cryptography.hazmat.primitives.asymmetric import ed25519

from juku_common.rules import Rules

META_KEY = "io.github.nabilrobert.juku/delegation"
CALLER_META_KEY = "io.github.nabilrobert.mcp-gateway/caller"


class RefusedError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class Grant:
    learner: str
    chain: tuple[str, ...]
    tools: frozenset[str]
    purpose: str
    run: str
    jti: str
    expires_at: datetime


@dataclass
class Signer:
    key: ed25519.Ed25519PrivateKey
    rules: Rules

    def mint(
        self, *, learner: str, agent: str, tools: list[str], purpose: str, run: str = "", now: datetime | None = None
    ) -> str:
        raise NotImplementedError

    def delegate(self, parent_token: str, *, to_agent: str, tools: list[str], now: datetime | None = None) -> str:
        raise NotImplementedError

    def sign_claims(self, claims: Mapping[str, Any]) -> str:
        raise NotImplementedError


@dataclass
class Verifier:
    public_key: ed25519.Ed25519PublicKey
    rules: Rules
    seen: dict[str, float] = field(default_factory=dict[str, float])

    def verify(self, token: str | None, tool: str, *, caller: str | None = None, now: datetime | None = None) -> Grant:
        raise NotImplementedError
