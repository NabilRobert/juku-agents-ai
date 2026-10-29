"""The gateway's allow-lists for Juku (ops/gateway/juku-routes.example.yaml) equal guardrails.yaml's agents."""

from typing import Any, cast

import pytest
import yaml
from juku_common.rules import Rules
from juku_testkit.databases import repo_root


def routes() -> dict[str, Any]:
    path = repo_root() / "ops" / "gateway" / "juku-routes.example.yaml"
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


@pytest.mark.guardrail("agents")
def test_each_agents_gateway_allow_list_equals_its_tools_in_the_rule_file(rules: Rules) -> None:
    config = routes()
    for agent, tools in rules.agents.items():
        policy = config["policies"][config["callers"][agent]["policy"]]
        assert set(policy["routes"]["juku"]["tools"]) == set(tools), agent


def test_every_agent_has_its_own_key() -> None:
    callers = routes()["callers"]
    assert len({caller["key_sha256"] for caller in callers.values()}) == len(callers)
