"""Shiori, the chat agent (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from juku_common.delegation import Signer
from juku_data.engine.models import Learner
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass
class ShioriRun:
    signer: Signer
    learner: Learner
    records: AsyncEngine
    tool_results: list[Any] = field(default_factory=list[Any])


def juku_toolset(url: str, gateway_key: str | None = None) -> MCPToolset:
    raise NotImplementedError


def build_shiori(model: Model, toolset: MCPToolset) -> Agent[ShioriRun, str]:
    raise NotImplementedError
