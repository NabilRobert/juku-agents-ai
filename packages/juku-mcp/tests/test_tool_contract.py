"""FF5: the tools' names, descriptions and input schemas are a contract, kept in a snapshot.

Changing a tool changes what every agent sees, so it must change the
snapshot (tests/snapshots/tools.json) in the same commit, where a reviewer
sees it. The schemas must also stay valid for strict-mode tool calling
(the lesson from MCP-backbone and the upstream strict-schema issue), and
no tool may take anything that names a learner (SM2).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

SNAPSHOT = Path(__file__).parent / "snapshots" / "tools.json"
# The JSON Schema keywords strict mode accepts, of those Juku uses.
STRICT_KEYWORDS = {"type", "properties", "required", "additionalProperties", "description", "items", "enum"}
LEARNER_WORDS = ("learner", "user", "public_id", "nickname", "sub")


async def listed_tools(client: Client) -> list[dict[str, Any]]:
    result = await client.list_tools()
    return [
        {"name": tool.name, "description": tool.description, "input_schema": tool.input_schema} for tool in result.tools
    ]


@pytest.mark.xfail(strict=True, reason="EDD: the server lands in the next commit")
@pytest.mark.fitness("FF5")
async def test_the_tools_match_their_snapshot(client: Client) -> None:
    assert await listed_tools(client) == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def check_strict(schema: dict[str, Any], where: str) -> None:
    unknown = set(schema) - STRICT_KEYWORDS
    assert not unknown, f"{where}: {unknown} isn't allowed in strict mode"
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False, f"{where}: needs additionalProperties: false"
        assert set(schema.get("required", [])) == set(schema.get("properties", {})), f"{where}: all must be required"
        for name, child in schema.get("properties", {}).items():
            check_strict(child, f"{where}.{name}")


@pytest.mark.fitness("FF5")
def test_every_snapshot_schema_is_strict_mode_valid() -> None:
    for tool in json.loads(SNAPSHOT.read_text(encoding="utf-8")):
        check_strict(tool["input_schema"], tool["name"])


@pytest.mark.fitness("FF8")
def test_no_tool_takes_anything_that_names_a_learner() -> None:
    for tool in json.loads(SNAPSHOT.read_text(encoding="utf-8")):
        for name in tool["input_schema"].get("properties", {}):
            assert not any(word in name.lower() for word in LEARNER_WORDS), f"{tool['name']} takes {name}"
