"""MEM1's tasks (evals/memory/suite.yaml), checked at $0: well-formed, answerable from the tools, gold from SQL.

The real run, Shiori answering each prompt, is paid and waits for slice 7
and Arthur's OK. What can be checked for free is checked here, for every
task: its fixture learner replays as the fixture says; the tools Shiori
must call return the facts the answer needs, and nothing it must not
claim; and its reference SQL returns the gold rows.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_mcp.server import build_server
from juku_mcp.tools import SPECS_BY_NAME
from juku_testkit.memory_fixtures import fixture_now, load_memory_fixture, load_suite
from mcp_helpers import call, connected, make_deps, token_for
from sqlalchemy import text

SUITE = load_suite()
TASKS = {str(task["id"]): task for task in SUITE["tasks"]}
CATEGORIES = {"knowledge_update", "temporal", "abstention"}
# The harness's graders (agent-eval-harness, agent_eval/suites.py: KNOWN_GRADERS).
HARNESS_GRADERS = {"result_match", "answer_match", "forbidden_tools", "required_tools"}


def required_tools(task: dict[str, Any]) -> list[str]:
    return [tool for grader in task["graders"] for tool in grader.get("required_tools", [])]


def test_the_suite_has_about_fifteen_tasks_in_the_benchmark_categories() -> None:
    tags = [tag for task in TASKS.values() for tag in task["tags"]]
    assert 14 <= len(TASKS) <= 16
    for category in CATEGORIES:
        assert tags.count(category) >= 3, category


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_each_task_is_in_the_harness_format(task_id: str) -> None:
    task = TASKS[task_id]
    assert SUITE["suite"] and SUITE["target"]
    assert task["prompt"].strip()
    for grader in task["graders"]:
        [(kind, spec)] = grader.items()
        assert kind in HARNESS_GRADERS
        if kind == "answer_match":
            assert spec["contains"], "answer_match needs something to look for"
    assert required_tools(task), "every memory task names the tools the answer must come from"
    assert set(required_tools(task)) <= set(SPECS_BY_NAME)


@pytest.mark.parametrize("task_id", sorted(TASKS))
async def test_each_task_is_answerable_from_the_tools_and_its_gold_comes_from_sql(
    task_id: str,
    engine_databases: Databases,
    rules: Rules,
    key: ed25519.Ed25519PrivateKey,
    signer: Signer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = TASKS[task_id]
    now: datetime = fixture_now()
    loaded = await load_memory_fixture(engine_databases, rules, str(task["learner"]), suffix=f"-{uuid.uuid4().hex[:6]}")
    monkeypatch.setattr("juku_mcp.server.utc_now", lambda: now)

    outputs: list[str] = []
    async with connected(build_server(make_deps(engine_databases, key, tmp_path / "audit.jsonl"))) as client:
        for tool in required_tools(task):
            answer = await call(client, tool, token_for(signer, loaded.learner))
            assert not answer.is_error, answer.text
            outputs.append(json.dumps(answer.body, ensure_ascii=False))
    seen = "\n".join(outputs)
    for fact in task.get("facts", []):
        assert fact in seen, f"{task_id}: the tools don't show {fact!r}"
    for claim in task.get("absent", []):
        assert claim not in seen, f"{task_id}: the tools show {claim!r}, which the answer must not claim"

    async with engine_databases.app.connect() as connection:
        rows = (await connection.execute(text(task["reference_sql"]), {"learner_id": loaded.learner.id})).mappings()
        gold = [{column: str(value) for column, value in row.items()} for row in rows]
    expected = [{column: str(value) for column, value in row.items()} for row in task["expected"]]
    assert gold == expected
