"""juku-ops' settings, from the environment (JUKU_*). See .env.example."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class OpsSettings(BaseSettings):
    # Secrets arrive as files named after the setting, e.g. /run/secrets/juku_ops_database_url.
    model_config = SettingsConfigDict(env_prefix="JUKU_", extra="ignore", secrets_dir="/run/secrets")

    # The jobs' own role: writes imports, heartbeats and job runs (ops/db/roles.sql).
    ops_database_url: str
    # Partition upkeep is DDL, so it runs as the role that owns the tables.
    migrator_database_url: str | None = None
    gateway_audit_log: Path | None = None
    juku_mcp_audit_log: Path | None = None
    # The heartbeat runs inside the app's container, so it asks the app on loopback.
    app_health_url: str = "http://127.0.0.1:8000/healthz"
