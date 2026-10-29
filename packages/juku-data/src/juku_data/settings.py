"""juku-data's settings, from the environment (JUKU_*) or, in a container, /run/secrets files."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SECRETS_DIR = Path("/run/secrets")


class DataSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="JUKU_", extra="ignore", secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None
    )

    # The app database, as the app's role (reads and writes learner data).
    app_database_url: str | None = None
    # The dict database: the owner loads it; everyone else reads it.
    dict_owner_database_url: str | None = None
    dict_database_url: str | None = None
    openjlpt_dir: Path = Path("data/raw/openjlpt-bf4e1ee")


def require(value: str | None, name: str) -> str:
    """A setting the command can't run without, or an error saying which variable to set."""
    if not value:
        raise SystemExit(f"JUKU_{name.upper()} is not set: add it to the environment (see ops/.env.example)")
    return value
