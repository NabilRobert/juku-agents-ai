"""Spike 6: mutation-check the token tests. Disables each check in
delegation.py in turn, runs the tests, and expects at least one to fail.
Restores the file afterwards. Usage: python mutate.py (from this folder)."""

import subprocess
import sys
from pathlib import Path

REQ = 'options={"require": REQUIRED}'
MUTANTS = [
    ("no token accepted", "if not token:", "if False:"),
    ("signature not checked", REQ, 'options={"require": REQUIRED, "verify_signature": False}'),
    ("audience not checked", REQ, 'options={"require": REQUIRED, "verify_aud": False}'),
    ("expiry not checked", REQ, 'options={"require": REQUIRED, "verify_exp": False}'),
    ("a minute of leeway", "leeway=0", "leeway=60"),
    ("unknown agents allowed", "any(agent not in AGENTS for agent in chain)", "False"),
    ("no depth limit", "len(chain) > MAX_AGENT_HOPS", "False"),
    ("scope not checked", 'tool not in claims["tools"]', "False"),
    ("hops not checked", "if len(chain) > 1:\n            self._check_hop", "if False:\n            self._check_hop"),
    ("parent on a direct chain allowed", 'elif "parent" in claims:', "elif False:"),
    ("caller not required", "if require_caller and caller is None:", "if False:"),
    ("caller not bound", 'if caller is not None and f"agent:{caller}" != chain[0]:', "if False:"),
    ("replay allowed", 'if claims["jti"] in self.seen:', "if False:"),
    ("any delegation path", "if tool_for_hop is None or len(chain) != 2:", "if False:"),
    ("parent not required", "if not isinstance(parent_token, str):", "if False:"),
    ("parent chain not compared", "if chain_of(parent) != chain[1:]:", "if False:"),
    ("learner may change", 'if parent["sub"] != claims["sub"]:', "if False:"),
    ("replan not required of the parent", 'if tool_for_hop not in parent["tools"]:', "if False:"),
    ("tools may widen", 'if not set(claims["tools"]) <= set(parent["tools"]):', "if False:"),
    ("expiry may extend", 'if claims["exp"] > parent["exp"]:', "if False:"),
]


def main() -> int:
    path = Path("delegation.py")
    original = path.read_text()
    survivors = 0
    try:
        for name, old, new in MUTANTS:
            assert original.count(old) >= 1, f"mutation target not found: {old!r}"
            path.write_text(original.replace(old, new, 1))
            run = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], capture_output=True, text=True
            )
            killed = run.returncode != 0
            survivors += not killed
            print(f"{'killed  ' if killed else 'SURVIVED'}  {name}")
    finally:
        path.write_text(original)
    print(f"{len(MUTANTS) - survivors}/{len(MUTANTS)} mutants killed")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
