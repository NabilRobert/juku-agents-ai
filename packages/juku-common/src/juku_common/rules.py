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


class Rules(Section):
    """The whole rule file."""

    version: int
    alerts: AlertThresholds
    fitness: dict[str, FitnessFunction]

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
