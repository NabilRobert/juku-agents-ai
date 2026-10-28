"""Run SAF1 both ways, directly and through the gateway, and write the results next to the prediction.

Called by run_through_gateway.sh, which exports the gateway at a commit
that includes P6 (`_meta` forwarded, the caller stamped). Everything here is throwaway: databases on the
local test Postgres, keys made for the run, logs in a temporary folder.

Usage: uv run python packages/juku-mcp/attacks/run.py <gateway source dir> <gateway python> <work dir>
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import uvicorn
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.audit_chain import GATEWAY_GENESIS, JUKU_MCP_GENESIS, verify_log
from juku_common.delegation import Signer
from juku_common.rules import Rules, load_rules
from juku_data.dictionary.load import load_dictionary
from juku_data.dictionary.source import verify_source
from juku_data.dictionary.sync import sync_index
from juku_data.engine import Databases, create_learner, mark_known
from juku_mcp.app import create_app
from juku_mcp.settings import McpSettings
from juku_testkit.databases import create_database, create_roles, drop_database, migrate_to_heads, openjlpt_dir
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import ALL_SHIORI_TOOLS, Target, World, planted_instruction, run_suite  # noqa: E402

ALL_KEIKO_TOOLS = [tool for tool in ALL_SHIORI_TOOLS if tool not in ("search_words", "request_replan")]


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def gateway_config(work: Path, juku_url: str, agent_keys: dict[str, str]) -> Path:
    """Each agent its own key and allow-list (ADR-018): Keiko's lacks search_words and request_replan."""
    policies = {"shiori": ALL_SHIORI_TOOLS, "keiko": ALL_KEIKO_TOOLS}
    config = {
        "upstreams": {"juku": {"transport": "http", "url": juku_url}},
        "callers": {
            agent: {"key_sha256": hashlib.sha256(key.encode()).hexdigest(), "policy": agent}
            for agent, key in agent_keys.items()
        },
        "policies": {
            agent: {"routes": {"juku": {"tools": {tool: {} for tool in tools}}}} for agent, tools in policies.items()
        },
        "detector": {"rules": True},
        "audit": {"path": str(work / "gateway-audit.jsonl"), "fsync": False},
    }
    path = work / "gateway.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


async def wait_for_port(port: int) -> None:
    for _ in range(100):
        try:
            _, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.close()
            return
        except OSError:
            await asyncio.sleep(0.1)
    raise RuntimeError(f"nothing listening on {port}")


async def build_world(app_url: str, dict_url: str, key: ed25519.Ed25519PrivateKey) -> World:
    db = Databases(app=create_async_engine(app_url), dictionary=create_async_engine(dict_url))
    try:
        await load_dictionary(db.dictionary, verify_source(openjlpt_dir()))
        await sync_index(db.dictionary, db.app)
        a = await create_learner(db, nickname="A", target_level=5)
        b = await create_learner(db, nickname="B", target_level=5)
        async with db.app.connect() as connection:
            words = list(
                await connection.scalars(
                    text("SELECT word_id FROM learning.dictionary_words ORDER BY word_id LIMIT 40")
                )
            )
        for word in words:
            await mark_known(db, a.id, str(word), datetime(2026, 11, 2, tzinfo=UTC))
        planted = " ".join(planted_instruction(b.public_id).values())
        async with db.dictionary.begin() as connection:
            await connection.execute(
                text("UPDATE ojlpt.sentence SET en = coalesce(en, '') || ' ' || :p"), {"p": planted}
            )
    finally:
        await db.app.dispose()
        await db.dictionary.dispose()
    return World(signer=Signer(key, load_rules()), learner_a=a.public_id, learner_b=b.public_id)


def with_caller_rule(rules: Rules, required: bool) -> Rules:
    return rules.model_copy(
        update={"delegation": rules.delegation.model_copy(update={"require_gateway_caller": required})}
    )


async def serve_juku(settings: McpSettings, rules: Rules, port: int) -> tuple[uvicorn.Server, asyncio.Task[None]]:
    server = uvicorn.Server(uvicorn.Config(create_app(settings, rules), port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    return server, task


async def stop(server: uvicorn.Server, task: asyncio.Task[None]) -> None:
    server.should_exit = True
    await task


def compare(results: dict[str, str], mode: str) -> dict[str, Any]:
    predicted = {
        attack["id"]: attack[mode]
        for attack in cast(dict[str, Any], yaml.safe_load((HERE / "prediction.yaml").read_text()))["attacks"]
    }
    rows = [
        {
            "attack": attack,
            "predicted": predicted[attack],
            "actual": results[attack],
            "as_predicted": predicted[attack] == results[attack],
        }
        for attack in predicted
    ]
    return {
        "mode": mode,
        "attacks": len(rows),
        "as_predicted": sum(row["as_predicted"] for row in rows),
        "succeeded": sum(row["actual"] == "succeeds" for row in rows),
        "seconds": results["_seconds"],
        "rows": rows,
    }


async def main(gateway_src: Path, gateway_python: Path, work: Path) -> None:
    key = ed25519.Ed25519PrivateKey.generate()
    agent_keys = {agent: secrets.token_urlsafe(32) for agent in ("shiori", "keiko")}
    app_db, dict_db = (
        await asyncio.to_thread(create_database, "juku_saf1_app"),
        await asyncio.to_thread(create_database, "juku_saf1_dict"),
    )
    try:
        await asyncio.to_thread(create_roles)
        await asyncio.to_thread(migrate_to_heads, app_db)
        world = await build_world(app_db.sqlalchemy_url, dict_db.sqlalchemy_url, key)
        pem = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        rules = load_rules()
        reports: list[dict[str, Any]] = []
        for mode in ("direct", "gateway"):
            juku_port = free_port()
            settings = McpSettings(
                app_database_url=app_db.sqlalchemy_url,
                dict_database_url=dict_db.sqlalchemy_url,
                delegation_public_key=pem.decode(),
                audit_log=work / f"juku-{mode}.jsonl",
            )
            juku, juku_task = await serve_juku(settings, with_caller_rule(rules, mode == "gateway"), juku_port)
            gateway: subprocess.Popen[bytes] | None = None
            try:
                if mode == "direct":
                    target = Target(mode="direct", url=f"http://127.0.0.1:{juku_port}/mcp")
                else:
                    gateway_port = free_port()
                    config = gateway_config(work, f"http://127.0.0.1:{juku_port}/mcp", agent_keys)
                    gateway = subprocess.Popen(  # noqa: S603 (the gateway's own interpreter, our own arguments)
                        [
                            str(gateway_python),
                            "-c",
                            "import sys; from mcp_gateway.cli import main; sys.argv[0] = 'mcp-gateway'; main()",
                            "serve",
                            "--config",
                            str(config),
                            "--port",
                            str(gateway_port),
                        ],
                        cwd=work,
                        env={**os.environ, "PYTHONPATH": str(gateway_src)},
                    )
                    await wait_for_port(gateway_port)
                    target = Target(
                        mode="gateway", url=f"http://127.0.0.1:{gateway_port}/mcp/juku/", agent_keys=agent_keys
                    )
                reports.append(compare(await run_suite(target, world), mode))
            finally:
                if gateway is not None:
                    gateway.terminate()
                    gateway.wait(timeout=10)
                await stop(juku, juku_task)
        chains = {
            "juku-direct": verify_log(work / "juku-direct.jsonl", genesis=JUKU_MCP_GENESIS).is_intact,
            "juku-gateway": verify_log(work / "juku-gateway.jsonl", genesis=JUKU_MCP_GENESIS).is_intact,
            "gateway": verify_log(work / "gateway-audit.jsonl", genesis=GATEWAY_GENESIS).is_intact,
        }
        for report in reports:
            report["audit_chains_intact"] = chains
            (HERE / f"results-{report['mode']}.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
            print(
                f"{report['mode']:8} {report['as_predicted']}/{report['attacks']} as predicted, "
                f"{report['succeeded']} succeeded, {report['seconds']} s"
            )
        print("audit chains intact:", chains)
    finally:
        await asyncio.to_thread(drop_database, app_db)
        await asyncio.to_thread(drop_database, dict_db)


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])))
