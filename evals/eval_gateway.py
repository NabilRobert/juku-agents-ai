"""The real gateway for a paid run, rules only (Arthur's OK of 2026-11-02): exported, started, stopped.

From a `git archive` of the pinned commit, so the gateway's checkout is never changed, with its own
venv. The config is the attack suite's: each agent its own key and allow-list, `detector: {rules: true}`.
"""

from __future__ import annotations

import secrets
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from juku_testkit.databases import repo_root
from juku_testkit.serving import free_port

sys.path.insert(0, str(repo_root() / "packages" / "juku-mcp" / "attacks"))

from run import GATEWAY_AUDIT_LOG as GATEWAY_AUDIT_LOG  # re-exported for eval_stack
from run import gateway_config, start_gateway, wait_for_port

# The commit the attack suite's results come from (packages/juku-mcp/attacks/README.md).
GATEWAY_REF = "66227a2"
GATEWAY_REPO = Path.home() / "Desktop" / "my-kerjaan-aku" / "mcp-gateway"


def export_gateway(ref: str, work: Path) -> Path:
    archive = subprocess.run(
        ["git", "-C", str(GATEWAY_REPO), "archive", ref, "src"],
        capture_output=True,
        check=True,
    )
    subprocess.run(["tar", "-x", "-C", str(work)], input=archive.stdout, check=True)
    return work / "src"


@asynccontextmanager
async def running_gateway(juku_url: str, ref: str, work: Path) -> AsyncIterator[tuple[str, dict[str, str]]]:
    """Yields the gateway's URL for Juku's route, and each agent's key."""
    keys = {agent: secrets.token_urlsafe(32) for agent in ("shiori", "keiko")}
    port = free_port()
    config = gateway_config(work, juku_url, keys)
    gateway = start_gateway(GATEWAY_REPO / ".venv" / "bin" / "python", export_gateway(ref, work), work, config, port)
    try:
        await wait_for_port(port)
        yield f"http://127.0.0.1:{port}/mcp/juku/", keys
    finally:
        gateway.terminate()
        gateway.wait(timeout=10)
