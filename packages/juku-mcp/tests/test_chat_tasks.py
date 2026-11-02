"""Q1's tasks (evals/chat/suite.yaml), checked at $0. The real run is paid, with Arthur's OK."""

from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_testkit.memory_fixtures import load_suite
from suite_checks import check_answerable, check_harness_format

CHAT_EVALS = Path(__file__).resolve().parents[3] / "evals" / "chat"
SUITE = load_suite(CHAT_EVALS)
TASKS = {str(task["id"]): task for task in SUITE["tasks"]}
NOW = datetime.fromisoformat(str(SUITE["fixture"]["now"]))
# Every tool a learner's question can need. request_replan changes data, and get_memory has MEM1's own suite.
TOPICS = {"progress", "plan", "mistakes", "activity", "recommend", "reading", "dictionary"}


def test_the_suite_has_about_forty_tasks_covering_every_topic_and_abstention() -> None:
    tags = [tag for task in TASKS.values() for tag in task["tags"]]
    assert 38 <= len(TASKS) <= 42
    assert tags.count("abstention") >= 5
    for topic in TOPICS:
        assert topic in tags, topic


@pytest.mark.parametrize("task_id", sorted(TASKS))
def test_each_task_is_in_the_harness_format(task_id: str) -> None:
    check_harness_format(SUITE, TASKS[task_id])


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
    await check_answerable(
        TASKS[task_id], NOW, engine_databases, rules, key, signer, tmp_path / "audit.jsonl", monkeypatch
    )
