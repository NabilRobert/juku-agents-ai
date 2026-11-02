"""The load test's stack: where it lives, and bringing it up with its 5,000 learners (run.py's `setup`)."""

from __future__ import annotations

import asyncio
import os
import secrets
import subprocess
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "load"
COMPOSE = ["docker", "compose", "-f", str(HERE / "compose.yaml")]
ADMIN_URL = "postgresql+asyncpg://postgres@127.0.0.1:55442"
CONSENT_VERSION = "2026-10-29"  # juku_app.consent.CONSENT_VERSION
# High enough that no budget cap refuses a scripted call: the load test measures the stack, not the budget.
UNCAPPED_USD = 100_000.0  # app.budget_pools.size_usd is numeric(12, 6): under a million


def sh(command: list[str], *, check: bool = True, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True, **kwargs)


def write_rules() -> None:
    """guardrails.yaml as the stack reads it: no gateway in front of juku-mcp, and no budget cap in the way."""
    rules = yaml.safe_load((ROOT / "guardrails.yaml").read_text(encoding="utf-8"))
    rules["delegation"]["require_gateway_caller"] = False
    for pool in ("reports_pool_usd", "chat_pool_usd", "chat_daily_global_usd"):
        rules["budget"][pool] = UNCAPPED_USD
    (BUILD / "guardrails.yaml").write_text(yaml.safe_dump(rules, sort_keys=False), encoding="utf-8")


def write_secret_files(folder: str, settings: dict[str, str]) -> None:
    """Each setting as a file named after it, the way Pydantic Settings reads /run/secrets."""
    target = BUILD / folder
    target.mkdir(parents=True, exist_ok=True)
    for name, value in settings.items():
        (target / name).write_text(value, encoding="utf-8")


def write_settings() -> None:
    """A fresh delegation key and session secret for this stack only; the database logins need no password."""
    key = ed25519.Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    write_secret_files(
        "app-secrets",
        {
            "juku_app_database_url": "postgresql+asyncpg://juku_app@db:5432/app",
            "juku_dict_database_url": "postgresql+asyncpg://juku_app@db:5432/dict",
            "juku_session_secret": secrets.token_urlsafe(32),
            "juku_delegation_signing_key": private_pem,
        },
    )
    write_secret_files(
        "mcp-secrets",
        {
            "juku_mcp_app_database_url": "postgresql+asyncpg://juku_mcp@db:5432/app",
            "juku_mcp_dict_database_url": "postgresql+asyncpg://juku_mcp@db:5432/dict",
            "juku_mcp_delegation_public_key": public_pem,
        },
    )


def build_images() -> None:
    sh(["docker", "build", "-q", "-f", "app/Dockerfile", "-t", "juku-app:local", "."], cwd=ROOT)
    sh(["docker", "build", "-q", "-f", "packages/juku-mcp/Dockerfile", "-t", "juku-mcp:local", "."], cwd=ROOT)


def prepare_databases() -> None:
    """The managed setup in miniature: roles, the two databases, migrations, the dictionary, then the learners."""
    os.environ["JUKU_TEST_ADMIN_URL"] = ADMIN_URL.replace("+asyncpg", "") + "/postgres"
    from juku_testkit.databases import create_named_database, create_roles, migrate_to_heads

    create_roles()
    app = create_named_database("app")
    create_named_database("dict")
    migrate_to_heads(app)
    asyncio.run(load_learners())


async def load_learners() -> None:
    from juku_data.dictionary.load import load_dictionary
    from juku_data.dictionary.source import verify_source
    from juku_data.dictionary.sync import sync_index
    from juku_data.synthetic import build_synthetic
    from juku_testkit.databases import require_openjlpt

    app = create_async_engine(f"{ADMIN_URL}/app")
    dictionary = create_async_engine(f"{ADMIN_URL}/dict")
    try:
        await load_dictionary(dictionary, verify_source(require_openjlpt()))
        await sync_index(dictionary, app)
        report = await build_synthetic(app)
        print(f"synthetic: {report.learners} learners, {report.events} events in {report.seconds:.0f} s")
        await sign_everyone_up(app)
    finally:
        await app.dispose()
        await dictionary.dispose()


async def sign_everyone_up(app: AsyncEngine) -> None:
    """What /mulai leaves behind for each learner: a consent on today's notice. And logins for the services."""
    async with app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.consents (learner_id, version, is_adult, accepts_service, accepts_aggregates,"
                " accepts_group_digest) SELECT id, :version, true, true, false, false FROM learning.learners"
            ),
            {"version": CONSENT_VERSION},
        )
        for role in ("juku_app", "juku_mcp", "juku_ops"):
            await connection.execute(text(f"ALTER ROLE {role} LOGIN"))
        await connection.execute(text("ANALYZE"))


def setup() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    write_rules()
    write_settings()
    build_images()
    sh([*COMPOSE, "up", "-d", "--wait", "db"])
    prepare_databases()
    sh([*COMPOSE, "up", "-d", "--wait", "juku-mcp", "app"])
