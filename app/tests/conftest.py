"""Fixtures for the app's tests: a learner of their own, and a clean budget record."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from juku_data.engine import Databases, create_learner
from juku_data.engine.models import Learner
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def learner(engine_databases: Databases) -> AsyncIterator[Learner]:
    made = await create_learner(engine_databases, nickname="tester", target_level=5)
    yield made
    async with engine_databases.app.begin() as connection:
        await connection.execute(text("DELETE FROM learning.learners WHERE id = :id"), {"id": made.id})


@pytest.fixture
async def clean_budget(app_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with app_engine.begin() as connection:
        await connection.execute(text("TRUNCATE app.model_calls"))
    yield app_engine
