"""Slice 7: run a suite's prompts on the real Shiori, and record the run in the harness's format.

    uv run python evals/run_suite.py chat --run-id scripted-1     # $0, a scripted model
    uv run python evals/run_suite.py memory --epochs 2 --run-id m1 --real \\
        --budget 0.20 --purpose "MEM1 baseline, Arthur's OK of <date>"           # paid

Why not `agent-eval run`: it drives Inspect's own agent over a fixed MCP server, and Juku needs a
fresh token per tool call, a fixture learner per task, and Shiori's real code path. So this calls
`juku_app.chat.ask` and reads what happened from Juku's own records, then grades with the harness's
graders and writes its run files, so `agent-eval report` and `compare` work on the result (ADR-028).

A real run needs `--real`, a `--purpose`, a `--budget` and a `--total-cap`, and goes through the
real gateway, rules only. It stops before a trial could cross what's left, and `paid-ledger.jsonl`
carries the spend across runs, so a rerun can't pass the cap either. It reads JUKU_MODEL_API_KEY from
.env. A scripted run has no gateway unless given `--through-gateway`. Everything runs in throwaway
test databases, with Juku's MCP server in this process.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from unittest import mock

from agent_eval.envfile import read_env_file
from agent_eval.grading import GRADER_VERSION
from agent_eval.records import task_hash, write_run
from eval_gateway import GATEWAY_REF
from eval_parts import pipeline_runner, pipeline_suite, safety_runner, safety_suite
from eval_records import build_meta, grade, worst_pipeline_call_usd, worst_trial_usd
from eval_stack import UNCAPPED_USD, AllowAll, Stack, eval_rules, running_stack
from juku_app.budget import BudgetGuard
from juku_app.chat import ChatServices, ask
from juku_app.shiori import build_shiori, juku_toolset
from juku_common.rules import load_rules
from juku_testkit.memory_fixtures import load_memory_fixture, load_suite, source_of
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
LEDGER_NAME = "paid-ledger.jsonl"
Effort = Literal["minimal", "low", "medium", "high"]
RunOne = Callable[[dict[str, Any], int], Awaitable[dict[str, Any]]]
RUNS = ROOT / "build" / "evals"
SUITE_FOLDERS = {"chat": ROOT / "evals" / "chat", "memory": ROOT / "evals" / "memory"}
REAL_MODEL = "gpt-5-mini"
REAL_BASE_URL = "https://ai.sumopod.com/v1"  # juku_app.settings.AppSettings.model_base_url
TOOLS_CALLED = "SELECT tool FROM monitoring.tool_calls WHERE learner_id = :learner ORDER BY called_at"
USAGE = """
SELECT coalesce(sum(input_tokens), 0), coalesce(sum(output_tokens), 0), coalesce(sum(cost_usd), 0)
FROM app.model_calls WHERE learner_id = :learner
"""


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


def real_model(env_file: Path, effort: Effort | None = None) -> Model:
    key = read_env_file(env_file).get("JUKU_MODEL_API_KEY")
    if not key:
        raise SystemExit(f"JUKU_MODEL_API_KEY isn't set in {env_file}: add it, or leave out --real")
    settings = OpenAIChatModelSettings(openai_reasoning_effort=effort) if effort else None
    return OpenAIChatModel(REAL_MODEL, provider=OpenAIProvider(base_url=REAL_BASE_URL, api_key=key), settings=settings)


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
        agent=build_shiori(model, juku_toolset(stack.mcp_url, stack.gateway_keys.get("shiori"))),
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
    # A turn the run limit or the budget stopped isn't a finished answer, so it can't pass, as in the
    # harness's own compare (agent_eval/compare/comparison.py). Reported by Project 10.
    finished = not error and not stopped
    strict = finished and all(grader["strict"] for grader in graders)
    lenient = finished and all(grader["lenient"] for grader in graders)
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


def spent_so_far(ledger: Path) -> float:
    """What every real run has cost, from the ledger each trial is added to as it ends."""
    if not ledger.is_file():
        return 0.0
    return sum(float(json.loads(line)["cost_usd"]) for line in ledger.read_text(encoding="utf-8").splitlines())


async def run_trials(  # noqa: PLR0913 (what bounds a run, each one separate)
    tasks: list[dict[str, Any]],
    epochs: int,
    run_one: RunOne,
    limit_usd: float | None,
    worst_usd: float,
    ledger: Path | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Every task, `epochs` times. Stops before a trial could cross `limit_usd`; says if it finished."""
    trials: list[dict[str, Any]] = []
    spent = 0.0
    for attempt in range(1, epochs + 1):
        for task in tasks:
            if limit_usd is not None and spent + worst_usd > limit_usd:
                print(f"stopped: ${spent:.4f} spent, and one more trial could pass ${limit_usd:.2f}", flush=True)
                return trials, False
            trial = await run_one(task, attempt)
            spent += float(trial["cost_usd"])
            trials.append(trial)
            if ledger is not None:
                ledger.parent.mkdir(parents=True, exist_ok=True)
                with ledger.open("a", encoding="utf-8") as lines:
                    lines.write(json.dumps({"task": trial["task_id"], "cost_usd": trial["cost_usd"]}) + "\n")
            print(f"{trial['task_id']} #{attempt}: {trial['outcome']}, ${spent:.4f} so far", flush=True)
    return trials, True


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", choices=[*sorted(SUITE_FOLDERS), "pipeline", "safety"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--real", action="store_true", help="call the real model: this spends money")
    parser.add_argument("--budget", type=float, help="US dollars for the whole run; required with --real")
    parser.add_argument("--purpose", help="what the run is for, and whose OK it has; required with --real")
    parser.add_argument("--total-cap", type=float, help="US dollars across every real run; required with --real")
    parser.add_argument("--effort", choices=["minimal", "low", "medium", "high"], help="the model's reasoning effort")
    parser.add_argument("--through-gateway", action="store_true", help="a scripted run on a real run's path")
    parser.add_argument("--gateway-ref", default=GATEWAY_REF, help="the mcp-security-gateway commit a real run uses")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)
    if args.real and (args.budget is None or args.total_cap is None or not args.purpose):
        parser.error("--real spends money: it needs --budget, --total-cap and --purpose")
    return args


def suite_and_text(name: str) -> tuple[dict[str, Any], str]:
    if name == "pipeline":
        return pipeline_suite()
    if name == "safety":
        return safety_suite()
    folder = SUITE_FOLDERS[name]
    return load_suite(folder), (folder / "suite.yaml").read_text(encoding="utf-8")


def chat_runner(stack: Stack, make_model: Callable[[dict[str, Any]], Model], now: datetime) -> RunOne:
    async def run_one(task: dict[str, Any], attempt: int) -> dict[str, Any]:
        return await run_trial(stack, task, attempt, make_model(task), now)

    return run_one


async def run(args: argparse.Namespace) -> Path:
    suite, suite_text = suite_and_text(args.suite)
    real = real_model(args.env_file, args.effort) if args.real else None
    limit = None
    ledger = None
    if args.real:
        ledger = RUNS / LEDGER_NAME
        limit = min(args.budget, args.total_cap - spent_so_far(ledger))
    worst = worst_pipeline_call_usd(load_rules()) if args.suite == "pipeline" else worst_trial_usd(load_rules())
    # Under the cap: the guard checks before each agent call, so the last call can't pass the limit.
    pool = max((limit or UNCAPPED_USD) - worst, 0.0)
    through_gateway = args.real or args.through_gateway
    rules = eval_rules(with_gateway=through_gateway, reports_pool_usd=pool)
    now = datetime.fromisoformat(str(suite["fixture"]["now"]))

    def make_model(task: dict[str, Any]) -> Model:
        return real if real is not None else scripted_model(task)

    async with running_stack(rules, gateway_ref=args.gateway_ref if through_gateway else None) as stack:
        if args.suite == "pipeline":
            run_one = pipeline_runner(stack, real)
        elif args.suite == "safety":
            run_one = await safety_runner(stack, real, now)
        else:
            run_one = chat_runner(stack, make_model, now)
        with mock.patch("juku_mcp.server.utc_now", lambda: now):  # the tools see the fixture's week
            trials, is_complete = await run_trials(suite["tasks"], args.epochs, run_one, limit, worst, ledger)
    run_dir = RUNS / args.run_id
    write_run(run_dir, build_meta(args.run_id, suite, suite_text, trials, is_complete, args), trials)
    return run_dir


if __name__ == "__main__":
    print(json.dumps({"run": str(asyncio.run(run(parse_arguments(sys.argv[1:]))))}))
