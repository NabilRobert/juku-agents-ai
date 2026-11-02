"""Slice 7: run a suite's prompts on the real Shiori, and record the run in the harness's format.

    uv run python evals/run_suite.py chat --run-id scripted-1     # $0, a scripted model
    uv run python evals/run_suite.py memory --epochs 2 --run-id m1 --real \\
        --budget 0.20 --purpose "MEM1 baseline, Arthur's OK of <date>"           # paid

Why not `agent-eval run`: it drives Inspect's own agent over a fixed MCP server, and Juku needs a
fresh token per tool call, a fixture learner per task, and Shiori's real code path. So this calls
`juku_app.chat.ask` and reads what happened from Juku's own records, then grades with the harness's
graders and writes its run files, so `agent-eval report` and `compare` work on the result (ADR-028).

A real run needs `--real`, a `--purpose` and a `--budget`, and stops before a trial could cross the
budget. It reads JUKU_MODEL_API_KEY from .env. Everything else runs in throwaway test databases,
with Juku's MCP server in this process, reached directly: the gateway isn't in the path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest import mock

from agent_eval.envfile import read_env_file
from agent_eval.grading import GRADER_VERSION
from agent_eval.records import task_hash, write_run
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from eval_records import build_meta, grade, worst_trial_usd
from juku_app.budget import BudgetGuard
from juku_app.chat import ChatServices, ask
from juku_app.moderation import Verdict
from juku_app.shiori import build_shiori, juku_toolset
from juku_common.delegation import Signer
from juku_common.rules import Rules, load_rules
from juku_data.dictionary.load import load_dictionary
from juku_data.dictionary.source import verify_source
from juku_data.dictionary.sync import sync_index
from juku_data.engine import Databases
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings
from juku_testkit.databases import create_database, create_roles, drop_database, migrate_to_heads, openjlpt_dir
from juku_testkit.memory_fixtures import load_memory_fixture, load_suite, source_of
from juku_testkit.serving import serving
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "build" / "evals"
SUITE_FOLDERS = {"chat": ROOT / "evals" / "chat", "memory": ROOT / "evals" / "memory"}
REAL_MODEL = "gpt-5-mini"
REAL_BASE_URL = "https://ai.sumopod.com/v1"  # juku_app.settings.AppSettings.model_base_url
# The eval's own learners mustn't trip the app's budget: `--budget` is the cap here.
UNCAPPED_USD = 100_000.0
UNCAPPED_QUESTIONS = 1_000_000
TOOLS_CALLED = "SELECT tool FROM monitoring.tool_calls WHERE learner_id = :learner ORDER BY called_at"
USAGE = """
SELECT coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0), coalesce(sum(cost_usd), 0)
FROM app.model_calls WHERE learner_id = :learner
"""


class AllowAll:
    """The moderation check is AG6's, tested on its own. It isn't what these tasks measure."""

    async def check(self, message: str) -> Verdict:
        assert message
        return Verdict(suggests_self_harm=False)


@dataclass(frozen=True)
class Stack:
    db: Databases
    rules: Rules
    signer: Signer
    mcp_url: str


def eval_rules() -> Rules:
    """The rule file, with no caller stamp to require (no gateway here) and no budget caps to hit."""
    rules = load_rules()
    budget = rules.budget.model_copy(
        update={
            "chat_pool_usd": UNCAPPED_USD,
            "chat_daily_global_usd": UNCAPPED_USD,
            "chat_daily_questions_per_learner": UNCAPPED_QUESTIONS,
        }
    )
    delegation = rules.delegation.model_copy(update={"require_gateway_caller": False})
    return rules.model_copy(update={"budget": budget, "delegation": delegation})


@asynccontextmanager
async def running_stack() -> AsyncIterator[Stack]:
    """Throwaway databases and Juku's MCP server, gone when the block ends."""
    key = ed25519.Ed25519PrivateKey.generate()
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    rules = eval_rules()
    app_db = await asyncio.to_thread(create_database, "juku_eval_app")
    dict_db = await asyncio.to_thread(create_database, "juku_eval_dict")
    db = Databases(
        app=create_async_engine(app_db.sqlalchemy_url), dictionary=create_async_engine(dict_db.sqlalchemy_url)
    )
    try:
        await asyncio.to_thread(create_roles)
        await asyncio.to_thread(migrate_to_heads, app_db)
        await load_dictionary(db.dictionary, verify_source(openjlpt_dir()))
        await sync_index(db.dictionary, db.app)
        with tempfile.TemporaryDirectory() as work:
            settings = McpSettings(
                app_database_url=app_db.sqlalchemy_url,
                dict_database_url=dict_db.sqlalchemy_url,
                delegation_public_key=pem.decode(),
                audit_log=Path(work) / "audit.jsonl",
            )
            async with serving(create_app(settings, rules)) as base_url:
                yield Stack(db=db, rules=rules, signer=Signer(key, rules), mcp_url=f"{base_url}/mcp")
    finally:
        await db.app.dispose()
        await db.dictionary.dispose()
        await asyncio.to_thread(drop_database, app_db)
        await asyncio.to_thread(drop_database, dict_db)


def required_tools(task: dict[str, Any]) -> list[str]:
    return [tool for grader in task["graders"] for tool in grader.get("required_tools", [])]


def scripted_model(task: dict[str, Any]) -> FunctionModel:
    """Calls the task's tools, then gives the answer its grader wants: $0, and proves the plumbing only."""
    wanted = [grader["answer_match"]["contains"] for grader in task["graders"] if "answer_match" in grader]
    answer = " ".join(item if isinstance(item, str) else item[0] for contains in wanted for item in contains)

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        called = [part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)]
        if called:
            return ModelResponse(parts=[TextPart(answer)])
        arguments = task.get("tool_arguments", {})
        tools = required_tools(task)
        return ModelResponse(parts=[ToolCallPart(tool_name=tool, args=arguments.get(tool, {})) for tool in tools])

    return FunctionModel(step)


def real_model(env_file: Path) -> Model:
    key = read_env_file(env_file).get("JUKU_MODEL_API_KEY")
    if not key:
        raise SystemExit(f"JUKU_MODEL_API_KEY isn't set in {env_file}: add it, or leave out --real")
    return OpenAIChatModel(REAL_MODEL, provider=OpenAIProvider(base_url=REAL_BASE_URL, api_key=key))


async def recorded_usage(stack: Stack, learner_id: int) -> tuple[list[str], int, int, float]:
    """What Juku's own records say the turn did: its tools, tokens and cost."""
    async with stack.db.app.connect() as connection:
        tools = [str(tool) for tool in await connection.scalars(text(TOOLS_CALLED), {"learner": learner_id})]
        input_tokens, output_tokens, cost = (await connection.execute(text(USAGE), {"learner": learner_id})).one()
    return tools, int(input_tokens), int(output_tokens), float(Decimal(cost))


async def run_trial(stack: Stack, task: dict[str, Any], attempt: int, model: Model, now: datetime) -> dict[str, Any]:
    """One prompt, one fresh copy of its fixture learner, one graded trial record."""
    name = str(task["learner"])
    loaded = await load_memory_fixture(
        stack.db, stack.rules, name, suffix=f"-{uuid.uuid4().hex[:6]}", source=source_of(name)
    )
    services = ChatServices(
        agent=build_shiori(model, juku_toolset(stack.mcp_url)),
        guard=BudgetGuard(stack.db.app, stack.rules),
        moderator=AllowAll(),
        signer=stack.signer,
        app=stack.db.app,
    )
    started = time.perf_counter()
    final_answer: str | None = None
    error: str | None = None
    stopped: str | None = None
    try:
        answer = await ask(services, loaded.learner, task["prompt"], now)
        final_answer, stopped = answer.text, answer.stopped_because
    except Exception as failure:  # a provider or tool failure says nothing about the agent: an `error` trial
        error = type(failure).__name__
    tools, input_tokens, output_tokens, cost = await recorded_usage(stack, loaded.learner.id)
    graders = grade(task, final_answer, tools)
    strict = not error and all(grader["strict"] for grader in graders)
    lenient = not error and all(grader["lenient"] for grader in graders)
    return {
        "task_id": str(task["id"]),
        "task_hash": task_hash(task),
        "attempt": attempt,
        "outcome": "error" if error else ("pass" if strict else "fail"),
        "strict": strict,
        "lenient": lenient,
        "error_kind": "provider_or_harness" if error else None,
        "error_message": error,
        "stop_reason": stopped or "completed",
        "grader_version": GRADER_VERSION,
        "graders": graders,
        "final_answer": final_answer,
        "tool_calls": [{"tool": tool} for tool in tools],
        "model_calls": [],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "seconds": round(time.perf_counter() - started, 3),
    }


async def run_trials(
    stack: Stack, suite: dict[str, Any], epochs: int, budget: float | None, make_model: Any
) -> tuple[list[dict[str, Any]], bool]:
    """Every task, `epochs` times. Stops before a trial could cross `budget`; says if it finished."""
    now = datetime.fromisoformat(str(suite["fixture"]["now"]))
    trials: list[dict[str, Any]] = []
    spent = 0.0
    with mock.patch("juku_mcp.server.utc_now", lambda: now):  # the tools see the fixture's week
        for attempt in range(1, epochs + 1):
            for task in suite["tasks"]:
                if budget is not None and spent + worst_trial_usd(stack.rules) > budget:
                    print(f"stopped: ${spent:.4f} spent, and one more trial could pass ${budget:.2f}", flush=True)
                    return trials, False
                trial = await run_trial(stack, task, attempt, make_model(task), now)
                spent += float(trial["cost_usd"])
                trials.append(trial)
                print(f"{trial['task_id']} #{attempt}: {trial['outcome']}, ${spent:.4f} so far", flush=True)
    return trials, True


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", choices=sorted(SUITE_FOLDERS))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--real", action="store_true", help="call the real model: this spends money")
    parser.add_argument("--budget", type=float, help="US dollars for the whole run; required with --real")
    parser.add_argument("--purpose", help="what the run is for, and whose OK it has; required with --real")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)
    if args.real and (args.budget is None or not args.purpose):
        parser.error("--real spends money: it needs --budget and --purpose")
    return args


async def run(args: argparse.Namespace) -> Path:
    folder = SUITE_FOLDERS[args.suite]
    suite = load_suite(folder)
    suite_text = (folder / "suite.yaml").read_text(encoding="utf-8")
    real = real_model(args.env_file) if args.real else None

    def make_model(task: dict[str, Any]) -> Model:
        return real if real is not None else scripted_model(task)

    async with running_stack() as stack:
        trials, is_complete = await run_trials(stack, suite, args.epochs, args.budget, make_model)
    run_dir = RUNS / args.run_id
    write_run(run_dir, build_meta(args.run_id, suite, suite_text, trials, is_complete, args), trials)
    return run_dir


if __name__ == "__main__":
    print(json.dumps({"run": str(asyncio.run(run(parse_arguments(sys.argv[1:]))))}))
