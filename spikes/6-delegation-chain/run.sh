#!/usr/bin/env bash
# Spike 6: run the attack suite three ways:
#   direct   the Juku server alone;
#   gateway  behind a local copy of mcp-gateway's main, unmodified;
#   patched  behind a copy with gateway-meta-passthrough.patch applied, and the
#            Juku server requiring the gateway's caller stamp.
# The gateway runs from copies exported with `git archive`; its checkout is
# never changed. Every key here is a test value made for this run.
#
# Usage: ./run.sh <spike venv python>   (writes results-*.json here)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
PY=${1:?python of a venv with mcp 2.3.0, pyjwt and cryptography}
GW_REPO=${GW_REPO:-$HOME/Desktop/my-kerjaan-aku/mcp-gateway}
GW_PY=$GW_REPO/.venv/bin/python
RUN=$(mktemp -d)
PIDS=()
cleanup() { for p in ${PIDS[@]+"${PIDS[@]}"}; do kill "$p" 2>/dev/null || true; done; rm -rf "$RUN"; }
trap cleanup EXIT
export PYTHONDONTWRITEBYTECODE=1

# Test keys: the app's signing key pair, and one gateway key per agent.
"$PY" - "$RUN" <<'EOF'
import hashlib, json, secrets, sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
run = Path(sys.argv[1])
key = ec.generate_private_key(ec.SECP256R1())
(run / "app_key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                     serialization.NoEncryption()))
(run / "app_pub.pem").write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                                serialization.PublicFormat.SubjectPublicKeyInfo))
keys = {a: secrets.token_urlsafe(32) for a in ("shiori", "keiko")}
(run / "keys.json").write_text(json.dumps(keys))
(run / "gateway.yaml").write_text(f"""
upstreams:
  juku: {{transport: http, url: "http://127.0.0.1:18761/mcp"}}
callers:
  shiori: {{key_sha256: "{hashlib.sha256(keys['shiori'].encode()).hexdigest()}", policy: shiori}}
  keiko: {{key_sha256: "{hashlib.sha256(keys['keiko'].encode()).hexdigest()}", policy: keiko}}
policies:
  shiori:
    routes: {{juku: {{tools: {{get_progress: {{}}, get_memory: {{}}, request_replan: {{}}}}}}}}
  keiko:
    routes: {{juku: {{tools: {{get_progress: {{}}, get_memory: {{}}}}}}}}
detector: {{rules: true}}
audit: {{path: {run / "gateway-audit.jsonl"}, fsync: false}}
""")
EOF

wait_port() { for _ in $(seq 1 50); do nc -z 127.0.0.1 "$1" 2>/dev/null && return 0; sleep 0.2; done; echo "port $1 never opened" >&2; return 1; }
start_juku() { # log, extra flag
  (cd "$HERE" && exec "$PY" juku_server.py 18761 "$RUN/app_pub.pem" "$1" ${2:-}) &
  PIDS+=($!); wait_port 18761
}
start_gateway() { # source dir
  (cd "$RUN" && PYTHONPATH="$1" exec "$GW_PY" -c 'import sys; from mcp_gateway.cli import main; sys.argv[0] = "mcp-gateway"; main()' \
    serve --config "$RUN/gateway.yaml" --port 18762) &
  PIDS+=($!); wait_port 18762
}
stop_all() { for p in ${PIDS[@]+"${PIDS[@]}"}; do kill "$p" 2>/dev/null || true; done; wait 2>/dev/null || true; PIDS=(); sleep 0.5; }
attack() { # mode, url, juku log, [gateway log]
  (cd "$HERE" && "$PY" attack.py "$1" "$2" "$RUN/app_key.pem" "$3" ${4:+"$4"} ${4:+"$RUN/keys.json"}) >"$HERE/results-$1.json"
}

# Exported copies of the gateway's main: as it is, and patched.
mkdir -p "$RUN/gw-main" "$RUN/gw-patched"
git -C "$GW_REPO" archive main src | tar -x -C "$RUN/gw-main"
git -C "$GW_REPO" archive main src | tar -x -C "$RUN/gw-patched"
(cd "$RUN/gw-patched" && patch -s -p1 <"$HERE/gateway-meta-passthrough.patch")
echo "gateway: main at $(git -C "$GW_REPO" rev-parse --short main)"

start_juku "$RUN/juku-direct.jsonl"
attack direct http://127.0.0.1:18761/mcp "$RUN/juku-direct.jsonl"
stop_all

start_juku "$RUN/juku-gateway.jsonl"
start_gateway "$RUN/gw-main/src"
attack gateway http://127.0.0.1:18762/mcp/juku/ "$RUN/juku-gateway.jsonl" "$RUN/gateway-audit.jsonl"
stop_all
"$GW_PY" -c "import sys; sys.path.insert(0, '$RUN/gw-main/src'); from pathlib import Path; from mcp_gateway.audit import verify_chain; print('gateway audit chain (unmodified):', verify_chain(Path('$RUN/gateway-audit.jsonl')) or 'verifies')"
mv "$RUN/gateway-audit.jsonl" "$RUN/gateway-audit-unmodified.jsonl"

start_juku "$RUN/juku-patched.jsonl" --require-caller
start_gateway "$RUN/gw-patched/src"
attack patched http://127.0.0.1:18762/mcp/juku/ "$RUN/juku-patched.jsonl" "$RUN/gateway-audit.jsonl"
stop_all
"$GW_PY" -c "import sys; sys.path.insert(0, '$RUN/gw-patched/src'); from pathlib import Path; from mcp_gateway.audit import verify_chain; print('gateway audit chain (patched):', verify_chain(Path('$RUN/gateway-audit.jsonl')) or 'verifies')"

# Keep the logs (no secrets in them: tokens appear only as hashes).
mkdir -p "$HERE/logs"
cp "$RUN"/juku-*.jsonl "$RUN"/gateway-audit*.jsonl "$HERE/logs/"
for m in direct gateway patched; do
  "$PY" -c "import json; r = json.load(open('$HERE/results-$m.json')); print(f\"{r['mode']:8} legit allowed {r['legit_allowed']}/{r['legit']}, attacks refused {r['attacks_refused']}/{r['attacks']}, attacks logged {r['attacks_logged']}/{r['attacks']}\")"
done
