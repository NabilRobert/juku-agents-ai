"""A scripted crew for the pipeline's tests ($0): FunctionModels that read the facts the run sends them.

Each agent's prompt is JSON (juku_app.pipeline.crew). The faithful crew
does what a good crew would: Keiko picks real candidates and cites the
facts, Nikki writes only numbers from the facts and cites them, Tadashi
approves. The planted crew returns a fixed output, whatever it's told.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.budget import BudgetGuard
from juku_app.consent import ConsentAnswers, record_consent
from juku_app.pipeline.crew import Crew, CrewModels, build_crew
from juku_app.pipeline.run import PipelineServices
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

ModelFunction = Callable[[list[ModelMessage], AgentInfo], ModelResponse]
RUN_DATE = "2026-11-08"
RUN_TIME = time(18, 0)


def sunday_evening(timezone: str, on: str = RUN_DATE) -> datetime:
    """Sunday 18:00 in the learner's own timezone: when their weekly run is due (AG2)."""
    return datetime.combine(datetime.fromisoformat(on).date(), RUN_TIME, tzinfo=ZoneInfo(timezone))


def prompt_of(messages: list[ModelMessage]) -> dict[str, Any]:
    """The JSON the run sent in its latest request."""
    for message in reversed(messages):
        if isinstance(message, ModelRequest):
            for part in reversed(message.parts):
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    return json.loads(part.content)
    raise AssertionError("no prompt in the messages")


def structured(info: AgentInfo, value: dict[str, Any]) -> ModelResponse:
    """A response that calls the agent's output tool with `value`."""
    return ModelResponse(parts=[ToolCallPart(tool_name=info.output_tools[0].name, args=value)])


def faithful_plan(facts: dict[str, Any]) -> dict[str, Any]:
    words = facts["candidates"]["words"][:2]
    return {
        "focus": [{"word_id": w["word_id"], "level": w["level"], "reason": f"Kata baru: {w['word']}."} for w in words],
        "review_word_ids": [item["word_id"] for item in facts["mistakes"]["items"]],
        "explanation": f"Minggu ini kamu menjawab {facts['activity']['quiz_answers']} kuis [ref:activity].",
        "note_proposals": [],
    }


def faithful_report(facts: dict[str, Any], plan: dict[str, Any]) -> str:
    activity, progress = facts["activity"], facts["progress"]
    lines = [
        f"Minggu ini kamu menjawab {activity['quiz_answers']} kuis "
        f"dan {activity['quiz_correct']} benar [ref:activity].",
        f"Sekarang kamu menguasai {progress['known_words']} kata [ref:progress].",
    ]
    for word in plan["focus"]:
        lines.append(f"Minggu depan, coba kata ini [ref:{word['word_id']}].")
    return " ".join(lines)


def faithful_keiko(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return structured(info, faithful_plan(prompt_of(messages)["facts"]))


def faithful_nikki(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    sent = prompt_of(messages)
    return ModelResponse(parts=[TextPart(faithful_report(sent["facts"], sent["plan"]))])


def approving_tadashi(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    return structured(info, {"grade": "A", "issues": [], "feedback": "Baik."})


def planted_keiko(plan: dict[str, Any]) -> ModelFunction:
    def keiko(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return structured(info, plan)

    return keiko


def planted_nikki(report: str) -> ModelFunction:
    def nikki(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(report)])

    return nikki


def crew_of(
    keiko: ModelFunction = faithful_keiko,
    nikki: ModelFunction = faithful_nikki,
    tadashi: ModelFunction = approving_tadashi,
) -> Crew:
    return build_crew(
        CrewModels(keiko=FunctionModel(keiko), nikki=FunctionModel(nikki), tadashi=FunctionModel(tadashi))
    )


def services_for(
    db: Databases, rules: Rules, crew: Crew, key: ed25519.Ed25519PrivateKey | None = None
) -> PipelineServices:
    """The run's services; `key` signs Keiko's tokens, so pass the one Juku's MCP server trusts when it's called."""
    return PipelineServices(
        db=db,
        rules=rules,
        guard=BudgetGuard(db.app, rules),
        signer=Signer(key or ed25519.Ed25519PrivateKey.generate(), rules),
        crew=crew,
    )


async def consented(db: Databases, learner: Learner) -> Learner:
    """A fixture learner as a real one is: signed up, on the current consent notice."""
    answers = ConsentAnswers(is_adult=True, accepts_service=True, accepts_aggregates=False, accepts_group_digest=False)
    await record_consent(db.app, learner.id, answers)
    return learner
