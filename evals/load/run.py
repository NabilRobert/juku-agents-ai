"""FF10: Juku's load test, $0. It builds the stack, measures it, and checks it against the recorded baseline.

    uv run --group load python evals/load/run.py setup     # images, Postgres, the 5,000 learners (about 10 min)
    uv run --group load python evals/load/run.py measure   # Locust steps, the weekly run, delegation, DB size
    uv run --group load python evals/load/run.py check     # FF10: the $0 path's median p95 against guardrails.yaml
    uv run --group load python evals/load/run.py down      # stop the stack and delete its data

The stack is evals/load/compose.yaml: the app and juku-mcp at their production memory caps, on 2 vCPUs
between them, and a Postgres the size of the managed plan. Everything it writes goes to build/load/
(git-ignored). The numbers measure the design on one laptop, not real use: see evals/load/results.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import median, quantiles
from typing import Any

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BUILD = ROOT / "build" / "load"
COMPOSE = ["docker", "compose", "-f", str(HERE / "compose.yaml")]
ADMIN_URL = "postgresql+asyncpg://postgres@127.0.0.1:55442"
APP_URL = "http://127.0.0.1:55480"
# The users on at once in each step, out of the 5,000 learners. The baseline step is FF10's.
STEPS = (50, 100, 200, 400)
STEP_SECONDS = 90
RAMP_SECONDS = 10
SAMPLE_SECONDS = 5
PIPELINE_SAMPLE = 300
DELEGATION_ROUNDS = 5000
CHECK_RUNS = 3
CONSENT_VERSION = "2026-10-29"  # juku_app.consent.CONSENT_VERSION
# High enough that no budget cap refuses a scripted call: the load test measures the stack, not the budget.
UNCAPPED_USD = 100_000.0  # app.budget_pools.size_usd is numeric(12, 6): under a million


def sh(command: list[str], *, check: bool = True, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, check=check, text=True, **kwargs)


# --- setup -------------------------------------------------------------------------------------------------------


def write_rules() -> None:
    """guardrails.yaml as the stack reads it: no gateway in front of juku-mcp, and no budget cap in the way."""
    rules = yaml.safe_load((ROOT / "guardrails.yaml").read_text(encoding="utf-8"))
    rules["delegation"]["require_gateway_caller"] = False
    for pool in ("reports_pool_usd", "chat_pool_usd", "chat_daily_global_usd"):
        rules["budget"][pool] = UNCAPPED_USD
    (BUILD / "guardrails.yaml").write_text(yaml.safe_dump(rules, sort_keys=False), encoding="utf-8")


def write_secret_files(folder: str, settings: dict[str, str]) -> None:
    """Each setting as a file named after it, the way Pydantic Settings reads /run/secrets."""
    target = BUILD / folder
    target.mkdir(parents=True, exist_ok=True)
    for name, value in settings.items():
        (target / name).write_text(value, encoding="utf-8")


def write_settings() -> None:
    """A fresh delegation key and session secret for this stack only; the database logins need no password."""
    key = ed25519.Ed25519PrivateKey.generate()
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    write_secret_files(
        "app-secrets",
        {
            "juku_app_database_url": "postgresql+asyncpg://juku_app@db:5432/app",
            "juku_dict_database_url": "postgresql+asyncpg://juku_app@db:5432/dict",
            "juku_session_secret": secrets.token_urlsafe(32),
            "juku_delegation_signing_key": private_pem,
        },
    )
    write_secret_files(
        "mcp-secrets",
        {
            "juku_mcp_app_database_url": "postgresql+asyncpg://juku_mcp@db:5432/app",
            "juku_mcp_dict_database_url": "postgresql+asyncpg://juku_mcp@db:5432/dict",
            "juku_mcp_delegation_public_key": public_pem,
        },
    )


def build_images() -> None:
    sh(["docker", "build", "-q", "-f", "app/Dockerfile", "-t", "juku-app:local", "."], cwd=ROOT)
    sh(["docker", "build", "-q", "-f", "packages/juku-mcp/Dockerfile", "-t", "juku-mcp:local", "."], cwd=ROOT)


def prepare_databases() -> None:
    """The managed setup in miniature: roles, the two databases, migrations, the dictionary, then the learners."""
    os.environ["JUKU_TEST_ADMIN_URL"] = ADMIN_URL.replace("+asyncpg", "") + "/postgres"
    from juku_testkit.databases import create_named_database, create_roles, migrate_to_heads

    create_roles()
    app = create_named_database("app")
    create_named_database("dict")
    migrate_to_heads(app)
    asyncio.run(load_learners())


async def load_learners() -> None:
    from juku_data.dictionary.load import load_dictionary
    from juku_data.dictionary.source import verify_source
    from juku_data.dictionary.sync import sync_index
    from juku_data.synthetic import build_synthetic
    from juku_testkit.databases import require_openjlpt

    app = create_async_engine(f"{ADMIN_URL}/app")
    dictionary = create_async_engine(f"{ADMIN_URL}/dict")
    try:
        await load_dictionary(dictionary, verify_source(require_openjlpt()))
        await sync_index(dictionary, app)
        report = await build_synthetic(app)
        print(f"synthetic: {report.learners} learners, {report.events} events in {report.seconds:.0f} s")
        await sign_everyone_up(app)
    finally:
        await app.dispose()
        await dictionary.dispose()


async def sign_everyone_up(app: AsyncEngine) -> None:
    """What /mulai leaves behind for each learner: a consent on today's notice. And logins for the services."""
    async with app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.consents (learner_id, version, is_adult, accepts_service, accepts_aggregates,"
                " accepts_group_digest) SELECT id, :version, true, true, false, false FROM learning.learners"
            ),
            {"version": CONSENT_VERSION},
        )
        for role in ("juku_app", "juku_mcp", "juku_ops"):
            await connection.execute(text(f"ALTER ROLE {role} LOGIN"))
        await connection.execute(text("ANALYZE"))


def setup() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    write_rules()
    write_settings()
    build_images()
    sh([*COMPOSE, "up", "-d", "--wait", "db"])
    prepare_databases()
    sh([*COMPOSE, "up", "-d", "--wait", "juku-mcp", "app"])


# --- measure -----------------------------------------------------------------------------------------------------


def percentiles(times: list[float]) -> dict[str, float]:
    if len(times) < 2:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    cuts = quantiles(times, n=100, method="inclusive")
    return {"p50": round(cuts[49], 1), "p95": round(cuts[94], 1), "p99": round(cuts[98], 1)}


def memory_mib(usage: str) -> float:
    """docker stats' "123.4MiB / 256MiB" → 123.4."""
    used = usage.split("/")[0].strip()
    for unit, factor in (("GiB", 1024.0), ("MiB", 1.0), ("KiB", 1 / 1024)):
        if used.endswith(unit):
            return float(used.removesuffix(unit)) * factor
    return float(used.removesuffix("B")) / 1024 / 1024


def sample_containers(peaks: dict[str, dict[str, float]], stop: threading.Event) -> None:
    """The highest memory and CPU each container reached while the step ran."""
    while not stop.wait(SAMPLE_SECONDS):
        listing = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for line in listing.splitlines():
            name, usage, cpu = line.split("\t")
            if not name.startswith("juku-load-"):
                continue
            peak = peaks.setdefault(name, {"memory_mib": 0.0, "cpu_percent": 0.0})
            peak["memory_mib"] = max(peak["memory_mib"], round(memory_mib(usage), 1))
            peak["cpu_percent"] = max(peak["cpu_percent"], float(cpu.rstrip("%")))


def restart_count() -> dict[str, int]:
    """Restarts and OOM kills: a container that hit its cap is killed and shows here."""
    counts: dict[str, int] = {}
    for service in ("app", "juku-mcp"):
        found = subprocess.run(
            ["docker", "inspect", "-f", "{{.RestartCount}} {{.State.OOMKilled}}", f"juku-load-{service}-1"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
        counts[service] = int(found[0]) + (found[1] == "true") if found else -1
    return counts


def locust_command(users: int, seconds: int) -> list[str]:
    return [
        *("locust", "-f", str(HERE / "locustfile.py"), "--headless", "--host", APP_URL),
        *("--users", str(users), "--spawn-rate", str(max(1, users // RAMP_SECONDS))),
        *("--run-time", f"{seconds}s", "--csv", str(BUILD / f"step-{users}"), "--only-summary"),
    ]


def run_step(users: int, seconds: int = STEP_SECONDS) -> dict[str, Any]:
    """One Locust run at `users` learners on at once: per-group latency, throughput, errors and container peaks."""
    out = BUILD / f"step-{users}.json"
    out.unlink(missing_ok=True)  # so a Locust that dies early can't pass off an older run's numbers as this one's
    environment = os.environ | {"JUKU_LOAD_OUT": str(out), "JUKU_LOAD_SECRETS": str(BUILD / "app-secrets")}
    peaks: dict[str, dict[str, float]] = {}
    stop = threading.Event()
    # Daemon, and stopped in `finally`: a live sampler would otherwise keep a crashed run's process alive for good.
    sampler = threading.Thread(target=sample_containers, args=(peaks, stop), daemon=True)
    sampler.start()
    started = time.monotonic()
    try:
        # Locust exits 1 if a single request failed. That's a result to record, not a reason to lose the run.
        locust = sh(locust_command(users, seconds), check=False, env=environment)
    finally:
        stop.set()
        sampler.join()
    elapsed = time.monotonic() - started
    groups = json.loads(out.read_text())
    return {
        "users": users,
        "seconds": round(elapsed),
        "locust_exit": locust.returncode,
        "groups": {
            name: {
                "requests": len(times),
                "per_second": round(len(times) / elapsed, 1),
                "failures": groups["failures"][name],
                **percentiles(times),
            }
            for name, times in groups["times_ms"].items()
        },
        "peaks": peaks,
        "restarts": restart_count(),
    }


async def database_size() -> dict[str, int]:
    engine = create_async_engine(f"{ADMIN_URL}/app")
    try:
        async with engine.connect() as connection:
            size = await connection.scalar(text("SELECT pg_database_size('app')"))
            events = await connection.scalar(text("SELECT count(*) FROM learning.learning_events"))
            return {"bytes": int(size or 0), "learning_events": int(events or 0)}
    finally:
        await engine.dispose()


def time_delegation() -> dict[str, float]:
    """Mint and verify one token, as Shiori's call and juku-mcp's check do, on this machine's CPU."""
    from juku_common.delegation import Signer, Verifier
    from juku_common.rules import load_rules

    rules = load_rules(BUILD / "guardrails.yaml")
    key = ed25519.Ed25519PrivateKey.generate()
    signer, verifier = Signer(key, rules), Verifier(key.public_key(), rules)
    mint_ms: list[float] = []
    verify_ms: list[float] = []
    for _ in range(DELEGATION_ROUNDS):
        started = time.perf_counter()
        token = signer.mint(learner="syn-1", agent="shiori", tools=["recommend_words"], purpose="chat")
        minted = time.perf_counter()
        verifier.verify(token, "recommend_words")
        mint_ms.append((minted - started) * 1000)
        verify_ms.append((time.perf_counter() - minted) * 1000)
    return {"mint_p50_ms": percentiles(mint_ms)["p50"], "verify_p50_ms": percentiles(verify_ms)["p50"]}


async def time_weekly_runs() -> dict[str, Any]:
    """The weekly run for a sample of learners, one after another as `juku run-weekly --due` runs them.

    The crew is the tests' scripted one (faithful Keiko and Nikki, approving Tadashi) with no model latency,
    so this is the pipeline's own cost per learner; results.md adds the model's time to project 5,000.
    """
    sys.path.insert(0, str(ROOT / "app" / "tests"))
    from juku_app.pipeline.run import run_weekly
    from juku_common.rules import load_rules
    from juku_data.engine import Databases, get_learner
    from pipeline_helpers import (  # pyright: ignore[reportMissingImports]  (on sys.path above)
        crew_of,
        services_for,
        sunday_evening,
    )

    rules = load_rules(BUILD / "guardrails.yaml")
    db = Databases(app=create_async_engine(f"{ADMIN_URL}/app"), dictionary=create_async_engine(f"{ADMIN_URL}/dict"))
    statuses: dict[str, int] = {}
    try:
        services = services_for(db, rules, crew_of())
        started = time.perf_counter()
        for number in range(1, PIPELINE_SAMPLE + 1):
            learner = await get_learner(db, f"syn-{number}")
            outcome = await run_weekly(services, learner, sunday_evening(learner.timezone))
            statuses[outcome.status] = statuses.get(outcome.status, 0) + 1
        seconds = time.perf_counter() - started
    finally:
        await db.app.dispose()
        await db.dictionary.dispose()
    return {"learners": PIPELINE_SAMPLE, "seconds": round(seconds, 1), "statuses": statuses}


def measure() -> None:
    before = asyncio.run(database_size())
    steps = [run_step(users) for users in STEPS]
    after = asyncio.run(database_size())
    results = {
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "steps": steps,
        "database": {"before": before, "after": after},
        "delegation": time_delegation(),
        "weekly_runs": asyncio.run(time_weekly_runs()),
    }
    (BUILD / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


# --- check -------------------------------------------------------------------------------------------------------


def check() -> None:
    """FF10: fail if the $0 path's median p95 is more than the allowed amount slower than the baseline.

    Three runs, because one run's p95 swings by more than the allowed amount on a shared machine (results.md).
    """
    from juku_common.rules import load_rules

    limits = load_rules().fitness["FF10"].thresholds
    users = int(limits["baseline_users"])
    runs = [run_step(users)["groups"]["$0 path"] for _ in range(CHECK_RUNS)]
    p95 = median(run["p95"] for run in runs)
    failures = sum(run["failures"] for run in runs)
    ceiling = limits["baseline_p95_ms"] * (1 + limits["allowed_regression"])
    print(f"FF10: $0 path median p95 {p95} ms at {users} learners on at once; ceiling {ceiling:.0f} ms")
    if p95 > ceiling or failures:
        raise SystemExit("FF10 failed: slower than the recorded baseline allows, or requests failed")


def down() -> None:
    sh([*COMPOSE, "down", "--volumes"])
    # Throwaway keys, but gitleaks scans ignored folders too, so leaving them would fail `make check`.
    for secrets_folder in ("app-secrets", "mcp-secrets"):
        shutil.rmtree(BUILD / secrets_folder, ignore_errors=True)


if __name__ == "__main__":
    commands = {"setup": setup, "measure": measure, "check": check, "down": down}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        raise SystemExit(f"usage: run.py {{{','.join(commands)}}}")
    commands[sys.argv[1]]()
