"""`juku-ops`: the jobs cron runs (ops/crontab, ADR-014).

    juku-ops heartbeat           every minute: a beat, only if the app answers
    juku-ops import-audit        every 5 minutes: verify and import the audit logs
    juku-ops ensure-partitions   daily: keep the next months' partitions ready

Each job but the heartbeat records its run in monitoring.job_runs. A job
that finds a problem exits with status 1, so cron's own mail or log shows
it too.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import typer
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from juku_ops.audit_import import AUDIT_SOURCES, ImportResult, import_audit_log
from juku_ops.heartbeat import beat, is_healthy
from juku_ops.jobs import recorded_run
from juku_ops.partitions import ensure_month_partitions
from juku_ops.settings import OpsSettings

app = typer.Typer(help="Juku's scheduled operations jobs.", no_args_is_help=True)


def _engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_size=1, max_overflow=0)


async def _heartbeat(settings: OpsSettings, source: str) -> bool:
    async with httpx.AsyncClient() as client:
        if not await is_healthy(client, settings.app_health_url):
            return False
    engine = _engine(settings.ops_database_url)
    try:
        await beat(engine, source)
    finally:
        await engine.dispose()
    return True


@app.command()
def heartbeat(source: str = typer.Option("app", help="The name the beat is recorded under.")) -> None:
    """Record a beat if the app's health endpoint answers."""
    settings = OpsSettings()  # pyright: ignore[reportCallIssue] (fields come from the environment)
    if not asyncio.run(_heartbeat(settings, source)):
        typer.echo(f"no beat: {settings.app_health_url} didn't answer 200", err=True)
        raise typer.Exit(1)


def _log_paths(settings: OpsSettings) -> dict[str, Path | None]:
    return {"gateway": settings.gateway_audit_log, "juku-mcp": settings.juku_mcp_audit_log}


async def _import_audit(settings: OpsSettings) -> list[ImportResult]:
    engine = _engine(settings.ops_database_url)
    results: list[ImportResult] = []
    try:
        async with recorded_run(engine, "import-audit"):
            for name, path in _log_paths(settings).items():
                if path is None:
                    continue
                results.append(await import_audit_log(engine, AUDIT_SOURCES[name], path))
    finally:
        await engine.dispose()
    return results


@app.command("import-audit")
def import_audit() -> None:
    """Verify each configured audit log's hash chain and import its new lines."""
    settings = OpsSettings()  # pyright: ignore[reportCallIssue]
    if not any(_log_paths(settings).values()):
        typer.echo("no audit log configured: set JUKU_GATEWAY_AUDIT_LOG and/or JUKU_JUKU_MCP_AUDIT_LOG", err=True)
        raise typer.Exit(1)
    results = asyncio.run(_import_audit(settings))
    for result in results:
        state = "intact" if result.is_intact else "NOT INTACT: " + "; ".join(result.problems)
        typer.echo(f"{result.source}: {result.lines_imported} new of {result.lines_total} lines, {state}")
    if not all(result.is_intact for result in results):
        raise typer.Exit(1)


async def _ensure_partitions(settings: OpsSettings, migrator_url: str) -> list[str]:
    ops_engine = _engine(settings.ops_database_url)
    owner_engine = _engine(migrator_url)
    try:
        async with recorded_run(ops_engine, "ensure-partitions"):
            return await ensure_month_partitions(owner_engine, datetime.now(UTC).date())
    finally:
        await ops_engine.dispose()
        await owner_engine.dispose()


@app.command("ensure-partitions")
def ensure_partitions() -> None:
    """Create the monthly partitions for the next few months."""
    settings = OpsSettings()  # pyright: ignore[reportCallIssue]
    if settings.migrator_database_url is None:
        typer.echo("JUKU_MIGRATOR_DATABASE_URL is not set: partitions are made by the tables' owner", err=True)
        raise typer.Exit(1)
    created = asyncio.run(_ensure_partitions(settings, settings.migrator_database_url))
    typer.echo(f"created {len(created)} partitions" + (f": {', '.join(created)}" if created else ""))
