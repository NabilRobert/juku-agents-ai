"""The app's settings: JUKU_* from the environment or, in its container, /run/secrets files (ops/compose.yaml)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_DIR = Path("/run/secrets")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JUKU_", extra="ignore", secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None
    )

    app_database_url: str
    dict_database_url: str
    session_secret: str
    # The app's Ed25519 key (PEM): it signs every delegation token (ADR-018).
    delegation_signing_key: str
    # Shiori reaches Juku's MCP server through the gateway's Juku route, with her own key.
    gateway_url: str = "http://mcp-gateway:8000"
    shiori_gateway_key: str | None = None
    # Sumopod's OpenAI-compatible API (ADR-011). Without a key, the chat answers that it isn't available.
    model_base_url: str = "https://ai.sumopod.com/v1"
    model_api_key: str | None = None
    model_name: str = "gpt-5-mini"
    # Indonesia's official mental-health line, checked by Arthur before launch (AG6).
    crisis_line: str = "(nomor belum diisi: lihat JUKU_CRISIS_LINE)"
    secure_cookies: bool = True

    @property
    def juku_mcp_url(self) -> str:
        return f"{self.gateway_url.rstrip('/')}/mcp/juku/"
