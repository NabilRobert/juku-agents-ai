"""The throwaway stack a suite runs on: databases, Juku's MCP server, and any gateway."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from eval_gateway import running_gateway
from juku_app.moderation import Verdict
from juku_common.delegation import Signer
from juku_common.rules import Rules, load_rules
from juku_data.dictionary.load import load_dictionary
from juku_data.dictionary.source import verify_source
from juku_data.dictionary.sync import sync_index
from juku_data.engine import Databases
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings
from juku_testkit.databases import create_database, create_roles, drop_database, migrate_to_heads, openjlpt_dir
from juku_testkit.serving import serving
from sqlalchemy.ext.asyncio import create_async_engine

# The eval's own learners mustn't trip the app's budget: `--budget` is the cap here.
UNCAPPED_USD = 100_000.0
UNCAPPED_QUESTIONS = 1_000_000


class AllowAll:
    """The moderation check is AG6's, tested on its own. It isn't what these tasks measure."""

    async def check(self, message: str) -> Verdict:
        assert message
        return Verdict(suggests_self_harm=False)


@dataclass(frozen=True)
class Stack:
    db: Databases
    rules: Rules
    signer: Signer
    mcp_url: str
    dictionary_url: str = ""
    gateway_keys: dict[str, str] = field(default_factory=dict[str, str])


def eval_rules(*, with_gateway: bool = False, reports_pool_usd: float = UNCAPPED_USD) -> Rules:
    """The rule file with no chat caps to hit. The caller stamp is required only with a gateway to add it."""
    rules = load_rules()
    budget = rules.budget.model_copy(
        update={
            "chat_pool_usd": UNCAPPED_USD,
            "chat_daily_global_usd": UNCAPPED_USD,
            "chat_daily_questions_per_learner": UNCAPPED_QUESTIONS,
            "reports_pool_usd": reports_pool_usd,
        }
    )
    delegation = rules.delegation.model_copy(update={"require_gateway_caller": with_gateway})
    return rules.model_copy(update={"budget": budget, "delegation": delegation})


@asynccontextmanager
async def running_stack(rules: Rules, *, gateway_ref: str | None = None) -> AsyncIterator[Stack]:
    """Throwaway databases, Juku's MCP server and any gateway, gone when the block ends."""
    key = ed25519.Ed25519PrivateKey.generate()
    pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    app_db = await asyncio.to_thread(create_database, "juku_eval_app")
    dict_db = await asyncio.to_thread(create_database, "juku_eval_dict")
    db = Databases(
        app=create_async_engine(app_db.sqlalchemy_url), dictionary=create_async_engine(dict_db.sqlalchemy_url)
    )
    try:
        await asyncio.to_thread(create_roles)
        await asyncio.to_thread(migrate_to_heads, app_db)
        await load_dictionary(db.dictionary, verify_source(openjlpt_dir()))
        await sync_index(db.dictionary, db.app)
        with tempfile.TemporaryDirectory() as work:
            settings = McpSettings(
                app_database_url=app_db.sqlalchemy_url,
                dict_database_url=dict_db.sqlalchemy_url,
                delegation_public_key=pem.decode(),
                audit_log=Path(work) / "audit.jsonl",
            )
            async with serving(create_app(settings, rules)) as base_url:
                signer = Signer(key, rules)
                juku_url = f"{base_url}/mcp"
                if gateway_ref is None:
                    yield Stack(db, rules, signer, juku_url, dict_db.sqlalchemy_url)
                    return
                async with running_gateway(juku_url, gateway_ref, Path(work)) as (gateway_url, keys):
                    yield Stack(db, rules, signer, gateway_url, dict_db.sqlalchemy_url, keys)
    finally:
        await db.app.dispose()
        await db.dictionary.dispose()
        await asyncio.to_thread(drop_database, app_db)
        await asyncio.to_thread(drop_database, dict_db)
