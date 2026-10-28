"""The rule file, `guardrails.yaml`, loaded and validated (ADR-019, ADR-023).

Every limit Juku enforces lives in that one committed file, so raising a
limit is a reviewed diff, never a silent edit. Services load it once at
start-up through `load_rules`; a missing key, a typo or a wrong type stops
start-up with a message naming the field, instead of running on a default.

This module holds the sections every service shares. Each section is a
frozen Pydantic model with `extra="forbid"`, so an unknown key is an error.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

RULES_PATH_ENV = "JUKU_RULES_PATH"
RULES_FILE_NAME = "guardrails.yaml"
SUPPORTED_VERSION = 1


class RulesError(Exception):
    """The rule file is missing or invalid. The message says which field and what to do."""


class Section(BaseModel):
    """The base of every section: strict and immutable once loaded."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class FitnessFunction(Section):
    """One fitness function (scale path, ADR-023) and its thresholds.

    `pending` means its slice hasn't landed yet; `until` names that slice, so
    the harness can report what is missing rather than silently skipping it.
    `checked_by` says which runner enforces it: most run in pytest, but the
    migration linter and the frontend budget run as their own tools.
    """

    title: str
    status: Literal["active", "pending"]
    until: str | None = None
    checked_by: Literal["pytest", "squawk", "lighthouse-ci", "agent-eval-harness", "locust"] = "pytest"
    thresholds: dict[str, float] = Field(default_factory=dict[str, float])

    @model_validator(mode="after")
    def _pending_names_its_slice(self) -> Self:
        if self.status == "pending" and not self.until:
            raise ValueError("a pending fitness function needs `until`: the slice that activates it")
        if self.status == "active" and self.until:
            raise ValueError("an active fitness function can't have `until`; delete it")
        return self


class AlertThresholds(Section):
    """When an alert fires (Phase 2 M5). Grafana's rule files must use the same numbers."""

    heartbeat_stale_seconds: int = Field(gt=0)
    tool_error_rate_per_hour: float = Field(gt=0, lt=1)


class PrivacyRules(Section):
    """Privacy floors (Phase 2 EV2, M4)."""

    min_learners_per_cell: int = Field(ge=2)


class Delegation(Section):
    """One allowed hop: `from_agent` may hand `to_agent` a narrower token through `via_tool`."""

    from_agent: str
    to_agent: str
    via_tool: str


class DelegationRules(Section):
    """ADR-018's token rules."""

    issuer: str
    audience: str
    token_ttl_seconds: int = Field(gt=0, le=300)
    max_agent_hops: int = Field(ge=1)
    require_gateway_caller: bool
    allowed_delegations: list[Delegation]


class ReplanRules(Section):
    """SM4: the one action tool's daily cap."""

    max_requests_per_day: int = Field(ge=1)


class BudgetRules(Section):
    """B1 and B2: prices, the two pools and the caps."""

    input_usd_per_million: float = Field(gt=0)
    output_usd_per_million: float = Field(gt=0)
    reports_pool_usd: float = Field(gt=0)
    chat_pool_usd: float = Field(gt=0)
    chat_daily_global_usd: float = Field(gt=0)
    chat_daily_questions_per_learner: int = Field(gt=0)
    chat_run_request_limit: int = Field(gt=0)
    chat_run_total_tokens_limit: int = Field(gt=0)
    report_run_request_limit: int = Field(gt=0)
    report_run_total_tokens_limit: int = Field(gt=0)
    alert_fractions: list[float]

    @model_validator(mode="after")
    def _daily_cap_fits_the_pool(self) -> Self:
        if self.chat_daily_global_usd > self.chat_pool_usd:
            raise ValueError("chat_daily_global_usd can't be more than the whole chat pool")
        if any(not 0 < fraction <= 1 for fraction in self.alert_fractions):
            raise ValueError("alert_fractions are shares of a pool, between 0 and 1")
        return self


class DatabaseRules(Section):
    """`database`: the provider's connection limit and each login role's share of it (ADR-016)."""

    connection_limit: int = Field(gt=0)
    reserved_for_admin: int = Field(ge=1)
    app_pool: int = Field(ge=1)
    app_dict_pool: int = Field(ge=1)
    app_commands: int = Field(ge=1)
    mcp_pool: int = Field(ge=1)
    mcp_dict_pool: int = Field(ge=1)
    ops_connections: int = Field(ge=1)
    migrator_connections: int = Field(ge=1)
    dict_owner_connections: int = Field(ge=1)
    grafana_connections: int = Field(ge=1)
    mcp_backbone_connections: int = Field(ge=1)

    @model_validator(mode="after")
    def _shares_fit_the_limit(self) -> Self:
        shares = sum(value for name, value in self if name != "connection_limit")
        if shares > self.connection_limit:
            raise ValueError(
                f"the shares add up to {shares} connections, more than connection_limit ({self.connection_limit}): "
                "lower a pool, or raise the limit if the provider's plan did"
            )
        return self


class Rules(Section):
    """The whole rule file."""

    version: int
    alerts: AlertThresholds
    privacy: PrivacyRules
    delegation: DelegationRules
    agents: dict[str, list[str]]
    replan: ReplanRules
    budget: BudgetRules
    database: DatabaseRules
    fitness: dict[str, FitnessFunction]

    @model_validator(mode="after")
    def _delegations_only_narrow(self) -> Self:
        for hop in self.delegation.allowed_delegations:
            for agent in (hop.from_agent, hop.to_agent):
                if agent not in self.agents:
                    raise ValueError(f"delegation names agent {agent!r}, which isn't under `agents`")
            if hop.via_tool not in self.agents[hop.from_agent]:
                raise ValueError(f"{hop.from_agent} can't delegate through {hop.via_tool}: it isn't one of its tools")
            widened = set(self.agents[hop.to_agent]) - set(self.agents[hop.from_agent])
            if widened:
                raise ValueError(f"{hop.to_agent} would get tools {hop.from_agent} lacks: {sorted(widened)}")
        return self

    def tools_of(self, agent: str) -> frozenset[str]:
        """The Juku tools this agent's tokens may name; none for an unknown agent."""
        return frozenset(self.agents.get(agent, []))

    @model_validator(mode="after")
    def _known_version(self) -> Self:
        if self.version != SUPPORTED_VERSION:
            raise ValueError(f"version {self.version} isn't supported; this code reads version {SUPPORTED_VERSION}")
        return self

    def fitness_function(self, ff_id: str) -> FitnessFunction:
        try:
            return self.fitness[ff_id]
        except KeyError:
            raise RulesError(f"{ff_id} isn't in guardrails.yaml's `fitness` section: add it there") from None

    def threshold(self, ff_id: str, name: str) -> float:
        """One fitness threshold, or an error naming the missing key."""
        thresholds = self.fitness_function(ff_id).thresholds
        if name not in thresholds:
            raise RulesError(f"{ff_id} has no threshold {name!r} in guardrails.yaml: add it under its `thresholds`")
        return thresholds[name]


def _field_path(location: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in location)


def default_rules_path() -> Path:
    """`$JUKU_RULES_PATH` if set; otherwise `guardrails.yaml` in the nearest folder above this file that has one."""
    from_env = os.environ.get(RULES_PATH_ENV)
    if from_env:
        return Path(from_env)
    for folder in Path(__file__).resolve().parents:
        candidate = folder / RULES_FILE_NAME
        if candidate.is_file():
            return candidate
    raise RulesError(f"can't find {RULES_FILE_NAME}: set {RULES_PATH_ENV} to its path")


def load_rules(path: Path | None = None) -> Rules:
    """Read and validate the rule file. Raises RulesError with the field at fault."""
    rules_path = path if path is not None else default_rules_path()
    try:
        raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RulesError(f"can't read the rule file {rules_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RulesError(f"the rule file {rules_path} isn't valid YAML: {exc}") from exc
    try:
        return Rules.model_validate(raw)
    except ValidationError as exc:
        problems = "; ".join(f"{_field_path(error['loc'])}: {error['msg']}" for error in exc.errors())
        raise RulesError(f"the rule file {rules_path} is invalid: {problems}") from exc
