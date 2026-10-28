"""Stub until the pipeline lands (EDD1): Keiko, Nikki and Tadashi as PydanticAI agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from juku_common.delegation import Signer
from juku_data.engine.models import Learner
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models import Model
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_app.pipeline.outputs import KeikoPlan, Review


@dataclass
class KeikoRun:
    """One Keiko run's context: who it acts for, and how its tool calls are authorized."""

    signer: Signer
    learner: Learner
    records: AsyncEngine
    purpose: str = "weekly"
    # For a replan, the chain starts with Shiori and is delegated to Keiko (ADR-018).
    via_shiori: bool = False
    tool_results: list[Any] = field(default_factory=list[Any])


@dataclass(frozen=True)
class Crew:
    keiko: Agent[KeikoRun, KeikoPlan]
    nikki: Agent[None, str]
    tadashi: Agent[None, Review]


@dataclass(frozen=True)
class CrewModels:
    keiko: Model
    nikki: Model
    tadashi: Model


def build_crew(models: CrewModels, toolset: MCPToolset | None = None) -> Crew:
    raise NotImplementedError
