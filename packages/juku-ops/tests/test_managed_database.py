"""The managed database (ADR-016, revised): no database container, TLS to the provider, and a connection budget.

The provider allows about 20 connections to the cluster. guardrails.yaml's
`database` section shares them out; each pool is fixed with no overflow,
and each login role's CONNECTION LIMIT in ops/db/roles.sql equals its
share, so Postgres refuses the connection that would pass it.
"""

import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from juku_common.rules import Rules, RulesError, load_rules
from juku_testkit.databases import repo_root
from sqlalchemy.ext.asyncio import AsyncEngine

OPS = repo_root() / "ops"
CONNECTION_LIMIT = re.compile(r"ALTER ROLE (\w+) CONNECTION LIMIT (\d+);")
PROVIDER_HOST = "db.example.invalid"
DATABASE_RULES = [
    "database.connection_limit",
    "database.reserved_for_admin",
    "database.app_pool",
    "database.app_dict_pool",
    "database.app_commands",
    "database.mcp_pool",
    "database.mcp_dict_pool",
    "database.ops_connections",
    "database.migrator_connections",
    "database.dict_owner_connections",
    "database.grafana_connections",
    "database.mcp_backbone_connections",
]


def enforces(*paths: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Mark a test with every rule it enforces, for G1."""

    def mark(test: Callable[..., None]) -> Callable[..., None]:
        for path in paths:
            test = pytest.mark.guardrail(path)(test)
        return test

    return mark


def load_yaml(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))


def role_limits() -> dict[str, int]:
    sql = (OPS / "db" / "roles.sql").read_text(encoding="utf-8")
    return {role: int(limit) for role, limit in CONNECTION_LIMIT.findall(sql)}


def pool_of(engine: AsyncEngine) -> tuple[int, int]:
    """(size, overflow) of an engine's queue pool, read without connecting."""
    pool: Any = engine.pool
    # QueuePool has no public getter for its overflow cap; overflow() is the current count.
    return pool.size(), pool._max_overflow


@enforces(*DATABASE_RULES)
def test_pools_that_add_up_to_more_than_the_providers_limit_are_refused_at_load(tmp_path: Path) -> None:
    raw = load_yaml(repo_root() / "guardrails.yaml")
    raw["database"]["app_pool"] += raw["database"]["connection_limit"]
    path = tmp_path / "guardrails.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(RulesError, match="connection_limit"):
        load_rules(path)


@enforces(*DATABASE_RULES[2:])
def test_each_login_role_is_capped_by_postgres_at_its_share(rules: Rules) -> None:
    budget = rules.database
    assert role_limits() == {
        "juku_app": budget.app_pool + budget.app_dict_pool + budget.app_commands,
        "juku_mcp": budget.mcp_pool + budget.mcp_dict_pool,
        "juku_ops": budget.ops_connections,
        "juku_migrator": budget.migrator_connections,
        "dict_owner": budget.dict_owner_connections,
        "grafana_reader": budget.grafana_connections,
        "mcp_backbone": budget.mcp_backbone_connections,
    }


@enforces("database.app_pool", "database.app_dict_pool")
def test_the_apps_pools_have_their_sizes_and_no_overflow(rules: Rules) -> None:
    from juku_app.cli import databases
    from juku_app.settings import AppSettings

    config = AppSettings.model_construct(
        app_database_url="postgresql+asyncpg://u@h/app", dict_database_url="postgresql+asyncpg://u@h/dict"
    )
    engines = databases(config, rules)
    assert pool_of(engines.app) == (rules.database.app_pool, 0)
    assert pool_of(engines.dictionary) == (rules.database.app_dict_pool, 0)


@enforces("database.app_commands")
def test_a_hand_run_command_takes_one_connection_with_no_overflow(rules: Rules) -> None:
    from juku_app.cli import command_databases
    from juku_app.settings import AppSettings

    config = AppSettings.model_construct(
        app_database_url="postgresql+asyncpg://u@h/app", dict_database_url="postgresql+asyncpg://u@h/dict"
    )
    engines = command_databases(config, rules)
    assert pool_of(engines.app) == (rules.database.app_commands, 0)
    assert pool_of(engines.dictionary) == (rules.database.app_commands, 0)


@enforces("database.mcp_pool", "database.mcp_dict_pool")
def test_the_mcp_servers_pools_have_their_sizes_and_no_overflow(rules: Rules) -> None:
    from juku_mcp.app import databases
    from juku_mcp.settings import McpSettings

    settings = McpSettings.model_construct(
        app_database_url="postgresql+asyncpg://u@h/app", dict_database_url="postgresql+asyncpg://u@h/dict"
    )
    engines = databases(settings, rules)
    assert pool_of(engines.app) == (rules.database.mcp_pool, 0)
    assert pool_of(engines.dictionary) == (rules.database.mcp_dict_pool, 0)


@enforces("database.grafana_connections")
def test_grafana_reaches_the_provider_over_tls_within_its_share(rules: Rules) -> None:
    datasource = load_yaml(OPS / "grafana" / "provisioning" / "datasources" / "monitoring.yaml")["datasources"][0]
    assert datasource["url"] == "$JUKU_DB_HOST:$JUKU_DB_PORT"
    assert datasource["jsonData"]["sslmode"] == "require"
    assert datasource["jsonData"]["maxOpenConns"] == rules.database.grafana_connections


def test_mcp_backbone_has_its_own_read_only_login_on_the_dictionary() -> None:
    sql = (OPS / "db" / "roles.sql").read_text(encoding="utf-8")
    assert "GRANT dict_reader TO juku_mcp, juku_app, mcp_backbone;" in sql
    assert "ALTER ROLE mcp_backbone SET default_transaction_read_only = on;" in sql


def test_compose_runs_no_database_container() -> None:
    compose = load_yaml(OPS / "compose.yaml")
    images = [str(service.get("image", "")) for service in compose["services"].values()]
    assert not any(image.startswith("postgres") for image in images)
    for name, service in compose["services"].items():
        assert "db" not in service.get("depends_on", {}), f"{name} still waits for a db container"


def test_juku_mcp_reaches_the_database_on_a_network_no_other_service_joins() -> None:
    compose = load_yaml(OPS / "compose.yaml")
    others = {
        network
        for name, service in compose["services"].items()
        if name != "juku-mcp"
        for network in service["networks"]
    }
    external = {name for name, network in compose["networks"].items() if network.get("external")}
    own = [network for network in compose["services"]["juku-mcp"]["networks"] if network not in others | external]
    assert own == ["mcp-db"]


def run_make_secrets(tmp_path: Path, env_file: str) -> subprocess.CompletedProcess[str]:
    ops = tmp_path / "ops"
    (ops / "secrets").mkdir(parents=True)
    # The key pair is made only when missing; LibreSSL (macOS) can't make Ed25519 keys, the server's OpenSSL can.
    for key in ("juku_delegation_signing_key", "juku_mcp_delegation_public_key"):
        (ops / "secrets" / key).write_text("placeholder\n", encoding="utf-8")
    shutil.copy(OPS / "make-secrets.sh", ops / "make-secrets.sh")
    (ops / ".env").write_text(env_file, encoding="utf-8")
    return subprocess.run(["bash", str(ops / "make-secrets.sh")], capture_output=True, text=True, check=False)  # noqa: S603, S607


def test_make_secrets_builds_urls_for_the_providers_host_with_tls(tmp_path: Path) -> None:
    result = run_make_secrets(tmp_path, f"JUKU_DB_HOST={PROVIDER_HOST}\nJUKU_DB_PORT=6543\n")
    assert result.returncode == 0, result.stderr
    secrets = tmp_path / "ops" / "secrets"
    password = (secrets / "juku_app_password").read_text(encoding="utf-8").strip()
    url = (secrets / "juku_app_database_url").read_text(encoding="utf-8")
    assert url == f"postgresql+asyncpg://juku_app:{password}@{PROVIDER_HOST}:6543/app?ssl=require"
    backbone = (secrets / "mcp_backbone_dict_database_url").read_text(encoding="utf-8")
    assert backbone.startswith("postgresql://mcp_backbone:")
    assert backbone.endswith(f"@{PROVIDER_HOST}:6543/dict?sslmode=require")
    assert not (secrets / "postgres_password").exists(), "the provider's admin password isn't Juku's to make"


def test_make_secrets_without_the_providers_host_says_what_to_set(tmp_path: Path) -> None:
    result = run_make_secrets(tmp_path, "JUKU_APP_PORT=8080\n")
    assert result.returncode != 0
    assert "JUKU_DB_HOST" in result.stderr
    assert not (tmp_path / "ops" / "secrets" / "juku_app_database_url").exists()


@pytest.mark.xfail(
    strict=True,
    reason="Known bug, waiting on Arthur's choice of fix: a command opens two engines (app and dict), "
    "each sized app_commands, so one command can hold 2 connections against a share of 1. JOURNEY, FF6.",
)
def test_the_running_app_and_one_hand_run_command_fit_juku_apps_connection_limit(rules: Rules) -> None:
    """The weekly run, `juku invite` and the nightly check are hand-run commands beside the app, all as juku_app."""
    from juku_app.cli import command_databases, databases
    from juku_app.settings import AppSettings

    config = AppSettings.model_construct(
        app_database_url="postgresql+asyncpg://u@h/app", dict_database_url="postgresql+asyncpg://u@h/dict"
    )
    engines = [*vars(databases(config, rules)).values(), *vars(command_databases(config, rules)).values()]
    worst_case = sum(size + overflow for size, overflow in map(pool_of, engines))
    assert worst_case <= role_limits()["juku_app"]
