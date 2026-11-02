"""MEM1's tasks (evals/memory/suite.yaml), checked at $0. The real run is paid, with Arthur's OK."""

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_testkit.memory_fixtures import fixture_now, load_suite
from suite_checks import check_answerable, check_harness_format

SUITE = load_suite()
TASKS = {str(task["id"]): task for task in SUITE["tasks"]}
CATEGORIES = {"knowledge_update", "temporal", "abstention"}


def test_the_suite_has_about_fifteen_tasks_in_the_benchmark_categories() -> None:
    tags = [tag for task in TASKS.values() for tag in task["tags"]]
    assert 14 <= len(TASKS) <= 16
    for category in CATEGORIES:
        assert tags.count(category) >= 3, category


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
        TASKS[task_id], fixture_now(), engine_databases, rules, key, signer, tmp_path / "audit.jsonl", monkeypatch
    )
