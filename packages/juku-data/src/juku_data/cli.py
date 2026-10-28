"""`juku-data`: rebuild the dictionary and look after learner state.

    juku-data fetch-dictionary   download the pinned OpenJLPT files and check them
    juku-data load-dictionary    rebuild the dict database from them (about 3 s)
    juku-data sync-index         copy the dictionary's index into the app database

After a load, run sync-index: the app's summaries read the mirror.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import httpx
import typer
from sqlalchemy.ext.asyncio import create_async_engine

from juku_data.dictionary.fetch import fetch_dictionary
from juku_data.dictionary.load import LoadReport, load_dictionary
from juku_data.dictionary.source import DictionaryError, verify_source
from juku_data.dictionary.sync import SyncReport, sync_index
from juku_data.settings import DataSettings, require

app = typer.Typer(help="Juku's dictionary and learner-state jobs.", no_args_is_help=True)


def settings() -> DataSettings:
    return DataSettings()


@app.command("fetch-dictionary")
def fetch_dictionary_command(
    to: Annotated[Path | None, typer.Option(help="Folder to put the files in.")] = None,
) -> None:
    """Download the pinned OpenJLPT files and check their SHA-256."""
    folder = to or settings().openjlpt_dir

    async def run() -> list[Path]:
        async with httpx.AsyncClient() as client:
            return await fetch_dictionary(folder, client)

    try:
        paths = asyncio.run(run())
    except DictionaryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo("fetched and checked: " + ", ".join(str(path) for path in paths))


async def _load(url: str, folder: Path) -> LoadReport:
    engine = create_async_engine(url)
    try:
        return await load_dictionary(engine, verify_source(folder))
    finally:
        await engine.dispose()


@app.command("load-dictionary")
def load_dictionary_command() -> None:
    """Rebuild the dict database from the pinned files, and say what changed."""
    config = settings()
    try:
        report = asyncio.run(
            _load(require(config.dict_owner_database_url, "dict_owner_database_url"), config.openjlpt_dir)
        )
    except DictionaryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    counts = ", ".join(f"{table} {count}" for table, count in report.row_counts.items())
    typer.echo(f"loaded OpenJLPT {report.commit[:7]} in {report.seconds:.1f} s: {counts}")
    typer.echo(
        f"reading index: {report.sentences_mapped} of {report.sentences_total} sentences, "
        f"{report.content_tokens_mapped} of {report.content_tokens} content tokens mapped"
    )
    if report.disappeared_ids:
        typer.echo(f"WORD IDS THAT DISAPPEARED ({len(report.disappeared_ids)}): {', '.join(report.disappeared_ids)}")


async def _sync(dict_url: str, app_url: str) -> SyncReport:
    dict_engine, app_engine = create_async_engine(dict_url), create_async_engine(app_url)
    try:
        return await sync_index(dict_engine, app_engine)
    finally:
        await dict_engine.dispose()
        await app_engine.dispose()


@app.command("sync-index")
def sync_index_command() -> None:
    """Copy the dictionary's index columns into the app database."""
    config = settings()
    report = asyncio.run(
        _sync(
            require(config.dict_database_url, "dict_database_url"), require(config.app_database_url, "app_database_url")
        )
    )
    typer.echo(f"mirrored {report.words} words, {report.word_kanji} word kanji, {report.kanji} kanji")
    if report.items_missing_from_dictionary:
        missing = report.items_missing_from_dictionary
        typer.echo(f"LEARNER ITEMS NOT IN THE DICTIONARY ({len(missing)}): {', '.join(missing)}")
        raise typer.Exit(1)
