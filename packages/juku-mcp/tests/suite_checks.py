"""The $0 checks every eval suite shares: well-formed tasks, answerable from the tools, gold from SQL.

The real runs, Shiori answering each prompt, are paid and wait for slice 7 and
Arthur's OK. What can be checked for free is checked here.
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
from juku_testkit.memory_fixtures import load_memory_fixture, source_of
from mcp_helpers import call, connected, make_deps, token_for
from sqlalchemy import text

# The harness's graders (agent-eval-harness, agent_eval/suites.py: KNOWN_GRADERS).
HARNESS_GRADERS = {"result_match", "answer_match", "forbidden_tools", "required_tools"}


def required_tools(task: dict[str, Any]) -> list[str]:
    return [tool for grader in task["graders"] for tool in grader.get("required_tools", [])]


def check_harness_format(suite: dict[str, Any], task: dict[str, Any]) -> None:
    assert suite["suite"] and suite["target"]
    assert task["prompt"].strip()
    for grader in task["graders"]:
        [(kind, spec)] = grader.items()
        assert kind in HARNESS_GRADERS
        if kind == "answer_match":
            assert spec["contains"], "answer_match needs something to look for"
    assert required_tools(task), "every task names the tools the answer must come from"
    assert set(required_tools(task)) <= set(SPECS_BY_NAME)


async def check_answerable(
    task: dict[str, Any],
    now: datetime,
    db: Databases,
    rules: Rules,
    key: ed25519.Ed25519PrivateKey,
    signer: Signer,
    audit_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tools show the facts the answer needs and nothing it must not claim, and the SQL gives the gold."""
    name = str(task["learner"])
    loaded = await load_memory_fixture(db, rules, name, suffix=f"-{uuid.uuid4().hex[:6]}", source=source_of(name))
    monkeypatch.setattr("juku_mcp.server.utc_now", lambda: now)

    outputs: list[str] = []
    async with connected(build_server(make_deps(db, key, audit_path))) as client:
        for tool in required_tools(task):
            arguments = task.get("tool_arguments", {}).get(tool)
            answer = await call(client, tool, token_for(signer, loaded.learner), arguments)
            assert not answer.is_error, answer.text
            outputs.append(json.dumps(answer.body, ensure_ascii=False))
    seen = "\n".join(outputs)
    for fact in task.get("facts", []):
        assert fact in seen, f"{task['id']}: the tools don't show {fact!r}"
    for claim in task.get("absent", []):
        assert claim not in seen, f"{task['id']}: the tools show {claim!r}, which the answer must not claim"

    async with db.app.connect() as connection:
        rows = (await connection.execute(text(task["reference_sql"]), {"learner_id": loaded.learner.id})).mappings()
        gold = [{column: str(value) for column, value in row.items()} for row in rows]
    expected = [{column: str(value) for column, value in row.items()} for row in task["expected"]]
    assert gold == expected
