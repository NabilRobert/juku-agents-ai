"""`juku`: run the app, and the jobs Arthur runs by hand.

    juku serve                     the web app (in its container)
    juku invite --count 10         make invite codes; they're shown once, and only their hashes are kept
    juku delete-learner PUBLIC_ID  "Hapus data saya" for someone who has lost their code
    juku render-previews           static copies of the pages, for Lighthouse CI (FF12)

The weekly pipeline (`juku run-weekly`) and memory consolidation
(`juku consolidate`) arrive with slices 6 and 4.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import FastAPI
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data import engine
from juku_data.engine import Databases
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.ext.asyncio import create_async_engine

from juku_app import invites, privacy
from juku_app.logs import configure_logging
from juku_app.moderation import PendingModerator
from juku_app.settings import AppSettings
from juku_app.telemetry import install_tracing
from juku_app.web import WebDeps, create_web_app

app = typer.Typer(help="Juku's web app and its hand-run jobs.", no_args_is_help=True)
CHAT_UNAVAILABLE = "Chat belum tersedia: kunci model belum diatur."


def settings() -> AppSettings:
    return AppSettings()  # pyright: ignore[reportCallIssue] (fields come from the environment)


def databases(config: AppSettings) -> Databases:
    return Databases(
        app=create_async_engine(config.app_database_url), dictionary=create_async_engine(config.dict_database_url)
    )


def chat_model(config: AppSettings) -> Model:
    """Sumopod's gpt-5-mini when a key is set; otherwise a stand-in that says chat isn't available yet."""
    if config.model_api_key:
        provider = OpenAIProvider(base_url=config.model_base_url, api_key=config.model_api_key)
        return OpenAIChatModel(config.model_name, provider=provider)

    def unavailable(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart(CHAT_UNAVAILABLE)])

    async def unavailable_stream(_messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str]:
        yield CHAT_UNAVAILABLE

    return FunctionModel(unavailable, stream_function=unavailable_stream)


def build_app(config: AppSettings) -> FastAPI:
    key = serialization.load_pem_private_key(config.delegation_signing_key.encode(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise SystemExit("JUKU_DELEGATION_SIGNING_KEY isn't an Ed25519 private key: make one with ops/make-secrets.sh")
    rules = load_rules()
    return create_web_app(
        WebDeps(
            db=databases(config),
            rules=rules,
            signer=Signer(key, rules),
            session_secret=config.session_secret,
            model=chat_model(config),
            juku_mcp_url=config.juku_mcp_url,
            shiori_gateway_key=config.shiori_gateway_key,
            moderator=PendingModerator(),
            crisis_line=config.crisis_line,
            secure_cookies=config.secure_cookies,
        )
    )


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Address to listen on.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Port to listen on.")] = 8000,
) -> None:
    """Run the web app."""
    configure_logging()
    install_tracing()
    uvicorn.run(build_app(settings()), host=host, port=port, log_level="warning")


@app.command()
def invite(count: Annotated[int, typer.Option(min=1, max=100, help="How many codes.")] = 1) -> None:
    """Make invite codes. They're printed once; only their hashes are stored."""
    config = settings()

    async def run() -> list[str]:
        db = databases(config)
        try:
            return await invites.issue_codes(db.app, count)
        finally:
            await db.app.dispose()
            await db.dictionary.dispose()

    for code in asyncio.run(run()):
        typer.echo(code)


@app.command("delete-learner")
def delete_learner(public_id: str) -> None:
    """Delete everything about one learner, on their request."""
    config = settings()

    async def run() -> dict[str, int]:
        db = databases(config)
        try:
            learner = await engine.get_learner(db, public_id)
            return await privacy.delete_learner(db.app, learner.id)
        finally:
            await db.app.dispose()
            await db.dictionary.dispose()

    removed = asyncio.run(run())
    typer.echo("deleted: " + ", ".join(f"{table} {count}" for table, count in removed.items()))


@app.command("render-previews")
def render_previews_command(
    out: Annotated[Path, typer.Option(help="Folder for the HTML files.")] = Path("build/previews"),
) -> None:
    """Render each page with sample data, beside the built islands, for Lighthouse CI."""
    from juku_app.previews import render_previews

    for path in render_previews(out):
        typer.echo(path)
