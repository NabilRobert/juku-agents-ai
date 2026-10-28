"""Shared fixtures for the engine's tests: the fixture learners, replayed once per run."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from juku_data.engine import Databases
from juku_data.engine.models import Learner

sys.path.insert(0, str(Path(__file__).parent))

from fixture_learners import FIXTURE_NAMES, FixtureLearner, load_fixture, replay


@pytest.fixture(scope="session")
async def fixtures_and_learners(
    mirrored_dictionary: None,  # noqa: ARG001 (needed for its effect: the mirror is synced)
    app_database: object,
    dictionary_database: object,
) -> dict[str, tuple[FixtureLearner, Learner]]:
    """Each fixture learner, replayed through the engine once, by name."""
    from juku_testkit.databases import TestDatabase
    from sqlalchemy.ext.asyncio import create_async_engine

    assert isinstance(app_database, TestDatabase) and isinstance(dictionary_database, TestDatabase)
    db = Databases(
        app=create_async_engine(app_database.sqlalchemy_url),
        dictionary=create_async_engine(dictionary_database.sqlalchemy_url),
    )
    replayed: dict[str, tuple[FixtureLearner, Learner]] = {}
    try:
        for name in FIXTURE_NAMES:
            fixture = await load_fixture(db.dictionary, name)
            replayed[name] = (fixture, await replay(db, fixture))
    finally:
        await db.app.dispose()
        await db.dictionary.dispose()
    return replayed


SYNTHETIC_PREFIX = "juku_synth_"


def synthetic_cache_key() -> str:
    """Changes whenever what the synthetic database holds could: the migrations, the engine, the generator."""
    import hashlib

    from juku_testkit.databases import repo_root, require_openjlpt

    root = repo_root()
    digest = hashlib.sha256()
    sources = sorted((root / "migrations").rglob("*.py")) + sorted(
        (root / "packages" / "juku-data" / "src").rglob("*.py")
    )
    for path in [*sources, require_openjlpt() / "openjlpt.sqlite"]:
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@pytest.fixture(scope="session")
def synthetic_database(dictionary_database: object) -> object:
    """The 5,000-learner database for FF1, built once and kept on the test server until its sources change."""
    import asyncio

    from juku_data.dictionary.sync import sync_index
    from juku_data.synthetic import build_synthetic
    from juku_testkit.databases import (
        TestDatabase,
        create_named_database,
        create_roles,
        database_names,
        drop_database,
        migrate_to_heads,
        rename_database,
        url_for,
    )
    from sqlalchemy.ext.asyncio import create_async_engine

    assert isinstance(dictionary_database, TestDatabase)
    name = SYNTHETIC_PREFIX + synthetic_cache_key()
    existing = database_names(SYNTHETIC_PREFIX)
    if name in existing:
        return TestDatabase(name=name, url=url_for(name))
    for stale in existing:
        drop_database(TestDatabase(name=stale, url=url_for(stale)))
    database = create_named_database(name + "_building")
    create_roles()
    migrate_to_heads(database)

    async def build() -> None:
        app = create_async_engine(database.sqlalchemy_url)
        dictionary = create_async_engine(dictionary_database.sqlalchemy_url)
        try:
            await sync_index(dictionary, app)
            await build_synthetic(app)
        finally:
            await app.dispose()
            await dictionary.dispose()

    try:
        asyncio.run(build())
    except BaseException:
        drop_database(database)
        raise
    # Renamed only once complete, so an interrupted build is never mistaken for a finished one.
    return rename_database(database, name)
