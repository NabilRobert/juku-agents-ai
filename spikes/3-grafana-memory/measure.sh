#!/usr/bin/env bash
# Spike 3: start Grafana with its provisioned data source and dashboard,
# check both work, then sample its memory while idle, after loading the
# dashboard, and idle again.
#
# Usage: ./measure.sh <memory limit, e.g. 256m or 2g> <idle seconds> > results-<limit>.txt
set -euo pipefail
cd "$(dirname "$0")"

LIMIT=${1:-256m}
IDLE_S=${2:-300}
export GRAFANA_MEM_LIMIT=$LIMIT

# A throwaway admin password, generated here and never printed.
SECRET_DIR=$(mktemp -d)
trap 'docker compose down -v >/dev/null 2>&1; rm -rf "$SECRET_DIR"' EXIT
head -c 24 /dev/urandom | base64 | tr -d '/+=' >"$SECRET_DIR/admin_password"
chmod 644 "$SECRET_DIR/admin_password"
export ADMIN_PASSWORD_FILE=$SECRET_DIR/admin_password

docker compose down -v >/dev/null 2>&1 || true
docker compose up -d >/dev/null 2>&1
CID=$(docker compose ps -q grafana)

api() { # GET or POST against Grafana's API, from inside its container.
  docker exec "$CID" sh -c "curl -sf -u admin:\"\$(cat /run/admin_password)\" -H 'Content-Type: application/json' $*"
}

for _ in $(seq 1 60); do
  api http://localhost:3000/api/health >/dev/null 2>&1 && break
  sleep 2
done

echo "limit=$LIMIT grafana=$(docker exec "$CID" grafana --version)"
echo "datasource health: $(api http://localhost:3000/api/datasources/uid/juku-monitoring/health)"
echo "dashboard: $(api http://localhost:3000/api/dashboards/uid/juku-tool-health | python3 -I -c 'import json,sys; d=json.load(sys.stdin)["dashboard"]; print(d["title"], "panels:", len(d["panels"]))')"

sample() { # label, seconds: one reading every 10 s
  local label=$1 secs=$2
  for _ in $(seq 1 $((secs / 10))); do
    # docker stats: cgroup usage minus inactive page cache. memory.stat: anon is
    # Grafana's own heap and stacks; file is page cache the kernel can drop.
    local stats anon file
    stats=$(docker stats --no-stream --format '{{.MemUsage}}' "$CID" | cut -d/ -f1 | tr -d ' ')
    anon=$(docker exec "$CID" awk '$1=="anon"{print int($2/1048576)}' /sys/fs/cgroup/memory.stat)
    file=$(docker exec "$CID" awk '$1=="file"{print int($2/1048576)}' /sys/fs/cgroup/memory.stat)
    echo "$label $(date -u +%H:%M:%S) stats=$stats anon_mib=$anon file_mib=$file"
    sleep 10
  done
}

sleep 60 # let start-up settle (migrations, provisioning)
sample idle "$IDLE_S"

# Load the dashboard 20 times: both panels' queries, as the browser would.
QUERY=$(python3 -I -c '
import json
d = json.load(open("dashboards/tool-health.json"))
qs = [dict(t, datasource=p["datasource"]) for p in d["panels"] for t in p["targets"]]
print(json.dumps({"from": "now-7d", "to": "now", "queries": qs}))')
for i in $(seq 1 20); do
  out=$(echo "$QUERY" | docker exec -i "$CID" sh -c 'curl -sf -u admin:"$(cat /run/admin_password)" -H "Content-Type: application/json" -X POST --data-binary @- http://localhost:3000/api/ds/query')
  [ "$i" = 1 ] && echo "query check: $(echo "$out" | python3 -I -c 'import json,sys; r=json.load(sys.stdin)["results"]; print({k: (v.get("status"), sum(len(f["data"]["values"][0]) for f in v["frames"] if f["data"]["values"])) for k, v in r.items()})')"
done
sample after-dashboard 60
sample idle-again 120

echo "restarts=$(docker inspect -f '{{.RestartCount}}' "$CID") oom_killed=$(docker inspect -f '{{.State.OOMKilled}}' "$CID") status=$(docker inspect -f '{{.State.Status}}' "$CID")"
