"""The web app (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from pydantic_ai.models import Model

from juku_app.moderation import Moderator


@dataclass(frozen=True)
class WebDeps:
    db: Databases
    rules: Rules
    signer: Signer
    session_secret: str
    model: Model
    juku_mcp_url: str
    shiori_gateway_key: str | None
    moderator: Moderator
    crisis_line: str
    secure_cookies: bool = True


def create_web_app(deps: WebDeps) -> FastAPI:
    raise NotImplementedError
