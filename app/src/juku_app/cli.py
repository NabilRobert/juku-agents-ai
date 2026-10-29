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
from collections import Counter
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from fastapi import FastAPI
from juku_common.delegation import Signer
from juku_common.rules import Rules, load_rules
from juku_data import engine
from juku_data.engine import Databases
from juku_ops.jobs import recorded_run
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from juku_app import invites, privacy
from juku_app.budget import BudgetGuard
from juku_app.connections import command_engine
from juku_app.logs import configure_logging
from juku_app.moderation import PendingModerator
from juku_app.pipeline.crew import CrewModels, build_crew, keiko_toolset
from juku_app.pipeline.feedback import JOB_NAME as FEEDBACK_JOB
from juku_app.pipeline.feedback import draft_feedback
from juku_app.pipeline.run import PipelineServices, RunOutcome, run_due
from juku_app.settings import AppSettings
from juku_app.telemetry import install_tracing
from juku_app.web import WebDeps, create_web_app

app = typer.Typer(help="Juku's web app and its hand-run jobs.", no_args_is_help=True)
CHAT_UNAVAILABLE = "Chat belum tersedia: kunci model belum diatur."


def settings() -> AppSettings:
    return AppSettings()  # pyright: ignore[reportCallIssue] (fields come from the environment)


def databases(config: AppSettings, rules: Rules) -> Databases:
    """The web app's pools: fixed sizes from the rule file, no overflow, so juku_app stays within its share."""
    budget = rules.database
    return Databases(
        app=create_async_engine(config.app_database_url, pool_size=budget.app_pool, max_overflow=0),
        dictionary=create_async_engine(config.dict_database_url, pool_size=budget.app_dict_pool, max_overflow=0),
    )


# The databases a command reads: the app's and the dictionary.
COMMAND_DATABASES = ("app", "dict")


def command_databases(config: AppSettings, rules: Rules) -> Databases:
    """A hand-run command's pools, beside the running app: its share of juku_app's connections, one per database.

    A command reads both databases, so it needs a connection for each; the share (app_commands) covers both.
    Each connection waits out a role at its limit briefly instead of failing (juku_app.connections).
    """
    per_database = max(1, rules.database.app_commands // len(COMMAND_DATABASES))
    return Databases(
        app=command_engine(config.app_database_url, per_database),
        dictionary=command_engine(config.dict_database_url, per_database),
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


def signing_key(config: AppSettings) -> ed25519.Ed25519PrivateKey:
    key = serialization.load_pem_private_key(config.delegation_signing_key.encode(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise SystemExit("JUKU_DELEGATION_SIGNING_KEY isn't an Ed25519 private key: make one with ops/make-secrets.sh")
    return key


def admin_ids(config: AppSettings) -> frozenset[str]:
    return frozenset(part.strip() for part in config.admin_public_ids.split(",") if part.strip())


def build_app(config: AppSettings) -> FastAPI:
    rules = load_rules()
    return create_web_app(
        WebDeps(
            db=databases(config, rules),
            rules=rules,
            signer=Signer(signing_key(config), rules),
            session_secret=config.session_secret,
            model=chat_model(config),
            juku_mcp_url=config.juku_mcp_url,
            shiori_gateway_key=config.shiori_gateway_key,
            moderator=PendingModerator(),
            crisis_line=config.crisis_line,
            secure_cookies=config.secure_cookies,
            admin_public_ids=admin_ids(config),
        )
    )


def pipeline_services(config: AppSettings) -> PipelineServices:
    """The weekly crew on the chat's model (ADR-011), Keiko reaching Juku's MCP server with her own key."""
    rules = load_rules()
    # A cron command beside the running app: the commands' share of juku_app's
    # connections (guardrails.yaml database.app_commands), not the app's pools.
    db = command_databases(config, rules)
    model = chat_model(config)
    crew = build_crew(
        CrewModels(keiko=model, nikki=model, tadashi=model),
        keiko_toolset(config.juku_mcp_url, config.keiko_gateway_key),
    )
    return PipelineServices(
        db=db, rules=rules, guard=BudgetGuard(db.app, rules), signer=Signer(signing_key(config), rules), crew=crew
    )


def ops_engine(config: AppSettings) -> AsyncEngine:
    if config.ops_database_url is None:
        raise SystemExit("JUKU_OPS_DATABASE_URL is not set: the pipeline's jobs record their runs as the jobs' role")
    return create_async_engine(config.ops_database_url, pool_size=1, max_overflow=0)


@app.command("run-weekly")
def run_weekly_command(
    due: Annotated[
        bool, typer.Option("--due", help="Run every learner whose Sunday 18:00 has come, and queued replans.")
    ] = False,
) -> None:
    """The weekly pipeline (cron, hourly): each due learner's report, then any replans Shiori queued."""
    if not due:
        raise SystemExit("run-weekly needs --due: it runs the learners whose weekly run is due")
    config = settings()
    services, ops = pipeline_services(config), ops_engine(config)

    async def run() -> list[RunOutcome]:
        try:
            return await run_due(services, ops, datetime.now(UTC))
        finally:
            await ops.dispose()
            await services.db.app.dispose()
            await services.db.dictionary.dispose()

    outcomes = asyncio.run(run())
    counts = Counter(outcome.status for outcome in outcomes)
    typer.echo(
        "weekly runs: " + (", ".join(f"{status} {count}" for status, count in sorted(counts.items())) or "none due")
    )


@app.command("draft-feedback")
def draft_feedback_command() -> None:
    """Draft prompt changes from last week's recurring issues, for Arthur (AG4). Nothing is applied."""
    config = settings()
    services, ops = pipeline_services(config), ops_engine(config)

    async def run() -> int:
        try:
            async with recorded_run(ops, FEEDBACK_JOB):
                drafts = await draft_feedback(services.db.app, chat_model(config), services.rules, datetime.now(UTC))
            return len(drafts)
        finally:
            await ops.dispose()
            await services.db.app.dispose()
            await services.db.dictionary.dispose()

    typer.echo(f"feedback drafts: {asyncio.run(run())} (see the Run Inspector; nothing is applied)")


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
        db = command_databases(config, load_rules())
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
        db = command_databases(config, load_rules())
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
