"""FF6: every fixture question's and report's input tokens stay under their ceilings, counted offline ($0).

Each model request carries the agent's instructions, its tool and output
definitions, and every message so far; a turn or a run sends several. A
scripted model counts each request exactly as PydanticAI assembles it,
with tiktoken's o200k_base (gpt-5-mini's encoding), and the test adds them
up: per chat question (Shiori, on MEM1's 15 fixture questions, with her real
tool calls to Juku's MCP server), and per weekly report (the crew's four
calls, on the pipeline's 10 fixture learners). No model is called.

The ceilings, and the values measured when they were set, are in
guardrails.yaml's `fitness.FF6.thresholds`.
"""

import json
import uuid
from datetime import datetime
from typing import Any

import pytest
import tiktoken
import yaml
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.pipeline.run import run_weekly
from juku_app.shiori import ShioriRun, build_shiori, juku_toolset
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_testkit.memory_fixtures import PIPELINE_EVALS, fixture_now, load_memory_fixture, load_suite
from pipeline_helpers import (
    approving_tadashi,
    consented,
    crew_of,
    faithful_keiko,
    faithful_nikki,
    services_for,
    sunday_evening,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

ENCODING = tiktoken.get_encoding("o200k_base")
EDD = pytest.mark.xfail(strict=True, reason="EDD: FF6's ceilings and the counter's fix land in the next commit")
QUESTIONS = {str(task["id"]): task for task in load_suite()["tasks"]}
PIPELINE = yaml.safe_load((PIPELINE_EVALS / "fixtures.yaml").read_text(encoding="utf-8"))
LEARNERS = {str(item["name"]): str(item["source"]) for item in PIPELINE["learners"]}


def tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def part_text(part: Any) -> str:
    """What one message part puts in front of the model."""
    if isinstance(part, ToolCallPart):
        return part.tool_name + part.args_as_json_str()
    if isinstance(part, ToolReturnPart):
        return part.tool_name + part.model_response_str()
    content = getattr(part, "content", "")
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)


def request_tokens(messages: list[ModelMessage], info: AgentInfo) -> int:
    """One request, as sent: the instructions, every tool and output definition, and every message so far."""
    definitions = [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters_json_schema}
        for tool in [*info.function_tools, *info.output_tools]
    ]
    total = tokens(info.instructions or "") + tokens(json.dumps(definitions, ensure_ascii=False))
    for message in messages:
        total += sum(tokens(part_text(part)) for part in message.parts)
    return total


class Meter:
    """Adds up every request a scripted model receives."""

    def __init__(self) -> None:
        self.total = 0

    def counting(self, respond: Any) -> Any:
        def counted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            self.total += request_tokens(messages, info)
            return respond(messages, info)

        return counted


def required_tools(task: dict[str, Any]) -> list[str]:
    return [tool for grader in task["graders"] for tool in grader.get("required_tools", [])]


def shiori_answering(task: dict[str, Any]) -> Any:
    """Calls the task's required tools, then answers from what they returned."""

    def respond(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        has_results = any(isinstance(part, ToolReturnPart) for message in messages for part in message.parts)
        if not has_results:
            return ModelResponse(parts=[ToolCallPart(tool_name=tool, args={}) for tool in required_tools(task)])
        return ModelResponse(parts=[TextPart("Menurut datamu, begitulah [ref:progress].")])

    return respond


@EDD
@pytest.mark.fitness("FF6")
@pytest.mark.parametrize("task_id", sorted(QUESTIONS))
async def test_a_fixture_questions_input_tokens_stay_under_the_ceiling(
    task_id: str,
    engine_databases: Databases,
    rules: Rules,
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = QUESTIONS[task_id]
    now: datetime = fixture_now()
    loaded = await load_memory_fixture(engine_databases, rules, str(task["learner"]), suffix=f"-{uuid.uuid4().hex[:6]}")
    monkeypatch.setattr("juku_mcp.server.utc_now", lambda: now)
    meter = Meter()
    shiori = build_shiori(FunctionModel(meter.counting(shiori_answering(task))), juku_toolset(juku_mcp_url))
    run = ShioriRun(signer=Signer(key, rules), learner=loaded.learner, records=engine_databases.app)
    await shiori.run(str(task["prompt"]), deps=run)
    print(f"FF6 question {task_id}: {meter.total} input tokens")
    assert meter.total <= rules.threshold("FF6", "question_input_tokens_max")


@EDD
@pytest.mark.fitness("FF6")
@pytest.mark.parametrize("name", sorted(LEARNERS))
async def test_a_fixture_reports_input_tokens_stay_under_the_ceiling(
    name: str, engine_databases: Databases, rules: Rules
) -> None:
    loaded = await load_memory_fixture(
        engine_databases, rules, name, suffix=f"-{uuid.uuid4().hex[:6]}", source=LEARNERS[name]
    )
    learner = await consented(engine_databases, loaded.learner)
    meter = Meter()
    crew = crew_of(
        keiko=meter.counting(faithful_keiko),
        nikki=meter.counting(faithful_nikki),
        tadashi=meter.counting(approving_tadashi),
    )
    outcome = await run_weekly(services_for(engine_databases, rules, crew), learner, sunday_evening(learner.timezone))
    assert outcome.status == "published"
    print(f"FF6 report {name}: {meter.total} input tokens")
    assert meter.total <= rules.threshold("FF6", "report_input_tokens_max")


def test_the_counts_use_gpt_5_minis_encoding() -> None:
    assert ENCODING.name == "o200k_base"


# --- the break-it pass on the counter itself ---


@EDD
def test_a_special_token_string_in_a_prompt_is_counted_as_plain_text() -> None:
    """A learner may type "<|endoftext|>"; tiktoken refuses special-token strings unless told to count them as text."""
    assert tokens("apa itu <|endoftext|>?") > tokens("apa itu ?")


def test_empty_and_japanese_text_are_counted() -> None:
    assert tokens("") == 0
    assert tokens("食べる、飲む、読む") > 0
