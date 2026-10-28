"""ops/compose.yaml keeps its promises (ADR-016): capped, unpublished, and the MCP server only behind the gateway."""

from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from juku_testkit.databases import repo_root

# ADR-016's caps, in MB; Grafana's from spike 3 (ADR-009).
MEMORY_CAPS_MB = {"app": 256, "juku-mcp": 128, "db": 384, "grafana": 384}


def compose() -> dict[str, Any]:
    path: Path = repo_root() / "ops" / "compose.yaml"
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def services() -> dict[str, dict[str, Any]]:
    return cast(dict[str, dict[str, Any]], compose()["services"])


def test_the_services_are_the_four_planned() -> None:
    assert set(services()) == set(MEMORY_CAPS_MB)


@pytest.mark.parametrize(("name", "cap_mb"), sorted(MEMORY_CAPS_MB.items()))
def test_every_container_has_its_hard_memory_cap_and_no_swap_beyond_it(name: str, cap_mb: int) -> None:
    service = services()[name]
    assert service["mem_limit"] == f"{cap_mb}m"
    assert service["memswap_limit"] == f"{cap_mb}m"


def test_juku_mcp_has_no_published_port() -> None:
    assert "ports" not in services()["juku-mcp"]


def test_juku_mcp_shares_no_network_with_the_app() -> None:
    all_services = services()
    assert set(all_services["juku-mcp"]["networks"]).isdisjoint(all_services["app"]["networks"])


def test_juku_mcp_is_reachable_only_on_the_gateways_upstream_network() -> None:
    networks = compose()["networks"]
    for name in services()["juku-mcp"]["networks"]:
        network = networks[name]
        assert network.get("internal") or network.get("external"), f"{name} would expose juku-mcp"


def test_the_database_is_never_published() -> None:
    assert "ports" not in services()["db"]


def test_published_ports_are_on_loopback_only() -> None:
    for name, service in services().items():
        for port in service.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{name} publishes {port} beyond loopback"


@pytest.mark.parametrize("name", ["app", "juku-mcp"])
def test_juku_containers_are_read_only_with_no_capabilities(name: str) -> None:
    service = services()[name]
    assert service["read_only"] is True
    assert service["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in service["security_opt"]


def test_no_secret_is_passed_as_an_environment_variable() -> None:
    for name, service in services().items():
        for key, value in service.get("environment", {}).items():
            looks_secret = any(word in key.lower() for word in ("password", "secret", "token", "key"))
            assert not looks_secret or key.endswith("__FILE") or key.endswith("_FILE"), f"{name}: {key}={value}"
