#!/usr/bin/env bash
# SAF1 both ways ($0, local): directly against Juku's server, and through
# mcp-security-gateway at GATEWAY_REF, which must include P6 (the gateway
# forwarding `_meta` and stamping the caller, merged as d89f20b). The
# gateway runs from a `git archive` export, with its own venv: its
# checkout and refs are never changed. Needs `make db-up` and the pinned
# OpenJLPT files. Writes results-direct.json and results-gateway.json here.
#
# Usage: GATEWAY_REF=66227a2 packages/juku-mcp/attacks/run_through_gateway.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
GATEWAY_REPO=${GATEWAY_REPO:-$HOME/Desktop/my-kerjaan-aku/mcp-gateway}
GATEWAY_REF=${GATEWAY_REF:-main}
GATEWAY_PYTHON=$GATEWAY_REPO/.venv/bin/python
# The gateway's merge of P6 (NabilRobert/mcp-security-gateway#6).
P6_MERGE=d89f20b
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

if ! git -C "$GATEWAY_REPO" merge-base --is-ancestor "$P6_MERGE" "$GATEWAY_REF" 2>/dev/null; then
  echo "the gateway at $GATEWAY_REF doesn't include P6 ($P6_MERGE): set GATEWAY_REF to a commit that does" >&2
  exit 1
fi
mkdir -p "$WORK/gateway"
git -C "$GATEWAY_REPO" archive "$GATEWAY_REF" src | tar -x -C "$WORK/gateway"
echo "gateway: $GATEWAY_REF at $(git -C "$GATEWAY_REPO" rev-parse --short "$GATEWAY_REF^{commit}")"

cd "$ROOT"
uv run --frozen python "$HERE/run.py" "$WORK/gateway/src" "$GATEWAY_PYTHON" "$WORK"
mkdir -p "$HERE/logs"
cp "$WORK"/*.jsonl "$HERE/logs/"
