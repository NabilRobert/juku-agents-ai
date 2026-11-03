"""A run's records in the harness's format: the grades, and the meta that `report` and `compare` read."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
from datetime import UTC, datetime
from typing import Any

from agent_eval.export import run_status, totals
from agent_eval.grading import grade_one
from agent_eval.records import task_hash
from juku_app.shiori import INSTRUCTIONS
from juku_common.rules import Rules, load_rules
from juku_data.dictionary.pin import OPENJLPT_COMMIT
from juku_testkit.memory_fixtures import SOURCES

HARNESS_MODEL_ID = "openai-api/sumopod/gpt-5-mini"  # the harness's prices.yaml key
PRICE_CHECKED = "2026-10-23"  # guardrails.yaml's budget section: update both with each price recheck


def grade(task: dict[str, Any], final_answer: str | None, tools_called: list[str]) -> list[dict[str, Any]]:
    """Every grader the task lists, in the shape the harness stores, so `compare` can regrade it."""
    graded: list[dict[str, Any]] = []
    for grader in task["graders"]:
        [(kind, spec)] = grader.items()
        inputs = {"final_answer": final_answer} if kind == "answer_match" else {"tools_called": tools_called}
        strict, lenient = grade_one(kind, spec, inputs)
        graded.append({"kind": kind, "spec": spec, "input": inputs, "strict": strict, "lenient": lenient})
    return graded


def worst_trial_usd(rules: Rules) -> float:
    """The most one trial can cost: its token cap, all priced as output, the dearer kind."""
    return rules.budget.chat_run_total_tokens_limit * rules.budget.output_usd_per_million / 1_000_000


def worst_pipeline_call_usd(rules: Rules) -> float:
    """The most one crew call can cost. The reports pool is checked before each call, so this is the overshoot."""
    return rules.budget.report_run_total_tokens_limit * rules.budget.output_usd_per_million / 1_000_000


def data_fingerprint() -> str:
    """The fixture learners and the dictionary's pin: a run on other data can't be compared."""
    digest = hashlib.sha256(OPENJLPT_COMMIT.encode())
    for folder in SOURCES.values():
        for path in sorted(folder.glob("*.yaml")):
            digest.update(path.read_bytes())
    return digest.hexdigest()


def budget_record(rules: Rules, args: argparse.Namespace) -> dict[str, Any]:
    return {
        "priced": True,
        "budget_usd": args.budget,
        "estimate_usd": None,
        "token_basis": "the run's token cap",
        "per_trial_cap_usd": worst_trial_usd(rules),
        "purpose": args.purpose,
    }


def price_record(rules: Rules) -> dict[str, Any]:
    return {
        "input": rules.budget.input_usd_per_million,
        "output": rules.budget.output_usd_per_million,
        "source": "guardrails.yaml, from Sumopod's table",
        "checked": PRICE_CHECKED,
    }


def build_meta(  # noqa: PLR0913 (the run's facts, each one recorded)
    run_id: str, suite: dict[str, Any], suite_text: str, trials: list[dict[str, Any]], is_complete: bool, args: Any
) -> dict[str, Any]:
    model = HARNESS_MODEL_ID if args.real else "scripted"
    rules = load_rules()
    return {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": run_status("success" if is_complete else "cancelled", trials),
        "inspect_status": "not_used",
        "suite": {
            "name": suite["suite"],
            "sha256": hashlib.sha256(suite_text.encode()).hexdigest(),
            "frozen": False,
            "task_hashes": {str(task["id"]): task_hash(task) for task in suite["tasks"]},
            "task_tags": {str(task["id"]): task.get("tags", []) for task in suite["tasks"]},
        },
        "budget": budget_record(rules, args) if args.real else None,
        "price": price_record(rules) if args.real else None,
        "target": {"name": "juku", "transport": "streamable-http", "address": "in-process"},
        "agent": {
            "model": model,
            "model_args": {"reasoning_effort": args.effort} if args.effort else {},
            "system_prompt_sha256": hashlib.sha256(INSTRUCTIONS.encode()).hexdigest(),
            "system_prompt": INSTRUCTIONS,
            "tool_allowlist": None,
            "limits": {"message_limit": None, "time_limit": None, "token_limit": None},
            "epochs": args.epochs,
        },
        "provenance": {
            "data_fingerprint": data_fingerprint(),
            "models_reported": [model],
            "harness_git": "a44cad4",
            "inspect_ai_version": importlib.metadata.version("inspect-ai"),
        },
        "export_version": 1,
        "totals": totals(trials),
    }
