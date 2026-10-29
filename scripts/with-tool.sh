#!/usr/bin/env bash
# Usage: scripts/with-tool.sh <tool> "<how to install>" <command...>
# Runs the command if <tool> is installed. Otherwise it skips with a note,
# or fails when JUKU_REQUIRE_TOOLS=1 (CI), so CI never skips a check.
set -euo pipefail
tool=$1 hint=$2
shift 2
if command -v "$tool" >/dev/null 2>&1; then
    exec "$@"
fi
if [[ "${JUKU_REQUIRE_TOOLS:-0}" == "1" ]]; then
    echo "FAIL: $tool is not installed ($hint)" >&2
    exit 1
fi
echo "skipped: $tool is not installed ($hint); CI runs it"
