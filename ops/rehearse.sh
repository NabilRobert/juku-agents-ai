#!/usr/bin/env bash
# Rehearses the server's stack on a laptop (slice 8), so the server step is
# only the same commands against the managed database. $0: there is no
# model key, and the model's address refuses connections.
#
#   ops/rehearse.sh up      secrets, dictionary files, images, database, migrations, the stack
#   ops/rehearse.sh check   the health checks, Grafana's data source and an alert, the gateway, every cron job once,
#                           the owner's commands
#   ops/rehearse.sh down    stop it and delete its volumes (every learner in it) and the secrets it made
#
# It writes ops/secrets/ through ops/make-secrets.sh, and refuses to if that
# folder holds secrets it didn't make (no REHEARSAL marker). It needs the
# gateway's image, mcp-gateway:local, built from mcp-gateway's deploy/. Heavy:
# it builds two images and runs five containers, so run it alone.
set -euo pipefail
cd "$(dirname "$0")"

COMPOSE=(docker compose --env-file rehearsal/rehearsal.env -f compose.yaml -f rehearsal/compose.yaml)
MARKER=secrets/REHEARSAL
APP_URL=http://127.0.0.1:58080
GRAFANA_URL=http://127.0.0.1:53000
# Grafana evaluates its rules every minute (rules.yaml), so an alert shows within two.
ALERT_WAIT_SECONDS=150

say() { printf '\n== %s\n' "$*"; }
fail() { echo "rehearsal failed: $*" >&2; exit 1; }

# macOS's own openssl (LibreSSL) can't make the Ed25519 delegation key; Homebrew's can.
# The server's openssl (OpenSSL 3) can, so make-secrets.sh itself doesn't need this.
use_an_openssl_with_ed25519() {
    openssl genpkey -algorithm ed25519 >/dev/null 2>&1 && return
    local brew_bin
    brew_bin="$(brew --prefix openssl 2>/dev/null)/bin"
    [[ -x $brew_bin/openssl ]] || fail "this openssl can't make Ed25519 keys: brew install openssl, then rerun"
    PATH="$brew_bin:$PATH"
}

make_rehearsal_secrets() {
    if [[ -d secrets && -n "$(ls -A secrets)" && ! -e $MARKER ]]; then
        fail "ops/secrets/ holds secrets the rehearsal didn't make: move them away first"
    fi
    use_an_openssl_with_ed25519
    mkdir -p secrets && touch $MARKER
    JUKU_DB_HOST=db JUKU_DB_PORT=5432 ./make-secrets.sh >/dev/null
    (
        umask 077
        cd secrets
        [[ -s rehearsal_db_superuser_password ]] || openssl rand -hex 24 >rehearsal_db_superuser_password
        # The four secrets that come from elsewhere on the server: stand-ins, and no model key.
        [[ -s telegram_bot_token ]] || echo "rehearsal-no-telegram" >telegram_bot_token
        [[ -s juku_shiori_gateway_key ]] || openssl rand -hex 32 >juku_shiori_gateway_key
        [[ -s juku_keiko_gateway_key ]] || openssl rand -hex 32 >juku_keiko_gateway_key
        : >juku_model_api_key
    )
    write_gateway_config
}

# The hash the gateway keeps for a caller: sha256 of the key as the app sends it (whitespace stripped, as
# pydantic-settings reads a secret file).
key_hash() { tr -d '[:space:]' <"$1" | shasum -a 256 | cut -d' ' -f1; }
unheld_key_hash() { openssl rand -hex 32 | shasum -a 256 | cut -d' ' -f1; }

# The gateway's config: Juku's own routes (gateway/juku-routes.example.yaml, which a test keeps equal to
# guardrails.yaml) with the callers' hashes filled in, then the settings its container needs (mcp-gateway's
# deploy/gateway.example.yaml). Nikki and Tadashi call no Juku tool, so theirs are hashes of keys nobody holds.
write_gateway_config() {
    (
        umask 077
        sed -e "s/<sha256 of Shiori's key>/$(key_hash secrets/juku_shiori_gateway_key)/" \
            -e "s/<sha256 of Keiko's key>/$(key_hash secrets/juku_keiko_gateway_key)/" \
            -e "s/<sha256 of Nikki's key>/$(unheld_key_hash)/" \
            -e "s/<sha256 of Tadashi's key>/$(unheld_key_hash)/" \
            gateway/juku-routes.example.yaml >secrets/gateway.yaml
        cat >>secrets/gateway.yaml <<'EOF'
# From mcp-gateway's deploy/gateway.example.yaml: the app calls it by its service name (else HTTP 421),
# rules-only detection, and the audit log in the folder the app's import-audit job reads.
allowed_hosts: ["mcp-gateway:*"]
detector: {rules: true}
audit: {path: /var/log/mcp-gateway/audit.jsonl, fsync: true}
EOF
    )
}

require_the_gateway_image() {
    docker image inspect mcp-gateway:local >/dev/null 2>&1 ||
        fail "no mcp-gateway:local image: build it in mcp-gateway's deploy/ (docker compose build), then rerun"
}

set_up_database() {
    "${COMPOSE[@]}" up -d --wait db
    # setup.sh runs inside the db container, where psql is, from a copy of
    # ops/db and ops/secrets that is deleted straight after.
    "${COMPOSE[@]}" cp db/. db:/tmp/rehearsal-db/
    "${COMPOSE[@]}" cp secrets/. db:/tmp/rehearsal-secrets/
    "${COMPOSE[@]}" exec -T -e PGHOST=127.0.0.1 -e PGUSER=postgres -e JUKU_SECRETS_DIR=/tmp/rehearsal-secrets \
        db bash /tmp/rehearsal-db/setup.sh
    "${COMPOSE[@]}" exec -T db rm -rf /tmp/rehearsal-db /tmp/rehearsal-secrets
}

# The dictionary's files, downloaded and checked as on the server, into compose.yaml's
# default JUKU_OPENJLPT_HOST_DIR (relative to ops/). Kept between rehearsals.
DICTIONARY_DIR=../data/raw/openjlpt-bf4e1ee

fetch_the_dictionary() {
    [[ -s $DICTIONARY_DIR/openjlpt.sqlite ]] && return
    uv run --frozen juku-data fetch-dictionary --to "$DICTIONARY_DIR"
}

load_schema_and_dictionary() {
    "${COMPOSE[@]}" run --rm --no-deps app \
        sh -c 'JUKU_MIGRATOR_DATABASE_URL="$(cat /run/secrets/juku_migrator_database_url)" alembic upgrade heads'
    "${COMPOSE[@]}" run --rm --no-deps app juku-data load-dictionary
    "${COMPOSE[@]}" run --rm --no-deps app juku-data sync-index
}

up() {
    say "secrets"; make_rehearsal_secrets
    say "dictionary files"; fetch_the_dictionary
    say "images"; require_the_gateway_image; "${COMPOSE[@]}" build app juku-mcp
    say "database"; set_up_database
    say "migrations and dictionary"; load_schema_and_dictionary
    say "the stack"; "${COMPOSE[@]}" up -d --wait
    echo "Up: the app at $APP_URL, Grafana at $GRAFANA_URL (admin, ops/secrets/grafana_admin_password)."
}

# The password goes to curl on stdin (-K -), not its arguments, where `ps` would show it.
grafana_get() {
    printf 'user = "admin:%s"\n' "$(cat secrets/grafana_admin_password)" | curl -fsS -K - "$GRAFANA_URL$1"
}

# The heartbeat alert, read before any heartbeat: its table is empty, so a
# working data source and rule make it fire, with no evaluation error.
wait_for_the_heartbeat_alert() {
    local waited=0 rule
    while ((waited < ALERT_WAIT_SECONDS)); do
        rule=$(grafana_get /api/prometheus/grafana/api/v1/rules |
            jq -c '.data.groups[].rules[] | select(.name == "Heartbeat stale") | {state, health}')
        [[ $rule == '{"state":"firing","health":"ok"}' ]] && { echo "Heartbeat stale: firing, health ok"; return; }
        sleep 10
        waited=$((waited + 10))
    done
    fail "the heartbeat alert didn't fire within ${ALERT_WAIT_SECONDS}s (last seen: ${rule:-nothing})"
}

check_grafana() {
    grafana_get /api/datasources/uid/juku-monitoring/health | jq -e '.status == "OK"' >/dev/null ||
        fail "Grafana can't query the database as grafana_reader"
    echo "data source: OK"
    echo "alert rules provisioned: $(grafana_get /api/v1/provisioning/alert-rules | jq length)"
    wait_for_the_heartbeat_alert
}

# Every job in ops/crontab, once, exactly as cron runs it: the words after $JUKU_COMPOSE.
# (fd 3, and stdin from /dev/null, so compose can't read the rest of the list.)
run_the_crontab_once() {
    local job words
    while IFS= read -r job <&3; do
        read -r -a words <<<"$job"
        echo "-- $job"
        "${COMPOSE[@]}" "${words[@]}" </dev/null || fail "$job"
    done 3< <(sed -n 's/^.*\$JUKU_COMPOSE //p' crontab)
}

# The web app must still be the one that started: a job that pushed it past
# its memory cap would have had it killed and restarted (found 2026-11-05).
check_the_app_was_not_restarted() {
    local restarts
    restarts=$(docker inspect --format '{{.RestartCount}}' "$("${COMPOSE[@]}" ps -q app)")
    [[ $restarts == 0 ]] || fail "the app restarted $restarts times during the jobs: see docker events for an oom"
    echo "the app wasn't restarted"
}

# The app reaches Juku's MCP server only through the gateway: refused without a key (not 421, the wrong
# allowed_hosts, nor a connection error), let in with Shiori's. From a container on the app's networks.
check_the_gateway() {
    "${COMPOSE[@]}" run --rm --no-deps -T app python - <<'EOF' || fail "the app can't reach Juku's tools through the gateway"
import httpx, pathlib, sys
url = "http://mcp-gateway:8000/mcp/juku/"
hello = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "rehearsal", "version": "0"}}}
accept = {"Accept": "application/json, text/event-stream"}
key = pathlib.Path("/run/secrets/juku_shiori_gateway_key").read_text().strip()
without, with_key = (httpx.post(url, json=hello, headers=accept | extra).status_code
                     for extra in ({}, {"Authorization": f"Bearer {key}"}))
print(f"gateway: {without} without a key, {with_key} with Shiori's")
sys.exit(0 if (without, with_key) == (401, 200) else 1)
EOF
}

check() {
    say "health"
    curl -fsS "$APP_URL/healthz" && echo
    "${COMPOSE[@]}" ps --format '{{.Service}}: {{.Health}}'
    say "Grafana"; check_grafana
    say "the gateway"; check_the_gateway
    say "cron jobs, once each"
    run_the_crontab_once
    say "the owner's commands, as docs/guide.md gives them"
    "${COMPOSE[@]}" run --rm --no-deps -T app juku invite --count 1 >/dev/null || fail "juku invite"
    echo "juku invite: a code was issued"
    "${COMPOSE[@]}" run --rm --no-deps -T app juku learners || fail "juku learners"
    check_the_app_was_not_restarted
    echo "Rehearsal passed. Not covered: a chat answer, which needs the model (rehearsal/real-model.yaml, with Arthur's OK)."
}

# The rehearsal's secrets go too, so its stand-in signing key isn't left on disk
# (where `gitleaks dir` in make check finds it). Only a folder it made: the marker.
down() {
    "${COMPOSE[@]}" down --volumes --remove-orphans
    [[ -e $MARKER ]] && rm -rf secrets
    return 0
}

case "${1:-}" in
up) up ;;
check) check ;;
down) down ;;
*) echo "usage: ops/rehearse.sh up|check|down" >&2; exit 2 ;;
esac
