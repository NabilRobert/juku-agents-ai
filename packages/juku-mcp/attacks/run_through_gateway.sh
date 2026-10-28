#!/usr/bin/env bash
# SAF1 both ways ($0, local): directly against Juku's server, and through a
# copy of mcp-security-gateway's main with spike 6's patch (forward _meta,
# stamp the caller), which is prerequisite P6 until the gateway's own fix
# lands. The gateway runs from a `git archive` export, with its own venv:
# its checkout is never changed. Needs `make db-up` and the pinned OpenJLPT
# files. Writes results-direct.json and results-gateway.json here.
#
# Usage: packages/juku-mcp/attacks/run_through_gateway.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
GATEWAY_REPO=${GATEWAY_REPO:-$HOME/Desktop/my-kerjaan-aku/mcp-gateway}
GATEWAY_PYTHON=$GATEWAY_REPO/.venv/bin/python
PATCH=$ROOT/spikes/6-delegation-chain/gateway-meta-passthrough.patch
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$WORK/gateway"
git -C "$GATEWAY_REPO" archive main src | tar -x -C "$WORK/gateway"
(cd "$WORK/gateway" && patch -s -p1 <"$PATCH")
echo "gateway: main at $(git -C "$GATEWAY_REPO" rev-parse --short main), with the _meta patch"

cd "$ROOT"
uv run --frozen python "$HERE/run.py" "$WORK/gateway/src" "$GATEWAY_PYTHON" "$WORK"
mkdir -p "$HERE/logs"
cp "$WORK"/*.jsonl "$HERE/logs/"
