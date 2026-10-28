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
