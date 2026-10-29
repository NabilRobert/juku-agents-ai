"""juku-mcp's settings: JUKU_MCP_* from the environment or, in its container, /run/secrets files."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_DIR = Path("/run/secrets")


class McpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JUKU_MCP_", extra="ignore", secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None
    )

    # Both as the juku_mcp role: read-only, JIT off (ops/db/roles.sql).
    app_database_url: str
    dict_database_url: str
    # The app's Ed25519 public key (PEM): the only key that can mint tokens this server accepts.
    delegation_public_key: str
    audit_log: Path = Path("/var/log/juku-mcp/audit.jsonl")
    # Host headers the MCP endpoint serves (DNS-rebinding protection). The gateway calls
    # http://juku-mcp:8000/mcp, so the service name must be listed; JSON list in the env.
    allowed_hosts: list[str] = ["juku-mcp:*", "127.0.0.1:*", "localhost:*"]
