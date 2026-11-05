#!/usr/bin/env bash
# Juku on Arthur's Mac (local-use mode): one command for the stack and its backups.
#
#   ops/local/juku.sh start            start the stack (and create the database volume the first time)
#   ops/local/juku.sh stop             stop it; nothing is deleted
#   ops/local/juku.sh status           each service and its health
#   ops/local/juku.sh backup           an encrypted dump of the learners' database into ~/Backups/juku
#   ops/local/juku.sh restore-check    restore the latest backup into a scratch database, compare, drop it
#   ops/local/juku.sh nightly          backup, then restore-check: what the nightly job runs
#   ops/local/juku.sh weekly           the weekly reports and Keiko's curriculum checks that are due
#   ops/local/juku.sh install-schedule `nightly` at 03:00 and `weekly` every hour (LaunchAgents; Arthur runs this)
#   ops/local/juku.sh compose ...      any other docker compose command, with the right files
#
# There is no `down`: it would stop the stack and, with -v, delete what a rehearsal made. To stop, use stop.
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose --env-file rehearsal/rehearsal.env -f compose.yaml -f rehearsal/compose.yaml -f local/use.yaml)
VOLUME=juku-local-pgdata
BACKUPS=${JUKU_BACKUP_DIR:-$HOME/Backups/juku}
KEY_DIR=${JUKU_KEY_DIR:-$HOME/Documents/JUKU-KEYS}
KEY=$KEY_DIR/juku-backup-age-key.txt
# Two weeks of nightly backups; older ones are deleted after a new one is written.
KEEP_DAYS=14
LEARNER_TABLES="learning.learners learning.learning_events app.chat_messages"
AGENTS_DIR=$HOME/Library/LaunchAgents
NIGHTLY_AT='<key>StartCalendarInterval</key><dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>0</integer></dict>'
# Hourly, as ops/crontab runs it on the server: a learner's week runs once its Sunday 18:00 has come, or
# once they open Juku with no run in the last 7 days (app/src/juku_app/curriculum_check.py).
HOURLY='<key>StartInterval</key><integer>3600</integer>'

fail() { echo "juku: $*" >&2; exit 1; }

db_container() { "${COMPOSE[@]}" ps -q db; }

start() {
    docker volume inspect "$VOLUME" >/dev/null 2>&1 || docker volume create "$VOLUME" >/dev/null
    "${COMPOSE[@]}" up -d --no-build --wait
}

# The age key that encrypts the backups: made once, kept outside the repo, never printed.
public_key() {
    [[ -s $KEY ]] || (umask 077 && mkdir -p "$KEY_DIR" && age-keygen -o "$KEY" 2>/dev/null)
    age-keygen -y "$KEY"
}

backup() {
    command -v age >/dev/null || fail "age isn't installed: brew install age"
    local container out
    container=$(db_container)
    [[ -n $container ]] || fail "the database isn't running: ops/local/juku.sh start"
    out="$BACKUPS/app-$(date +%Y%m%d-%H%M%S).dump.age"
    (
        # Readable only by Arthur, like the key: encrypted, but still his learners' data.
        umask 077
        mkdir -p "$BACKUPS"
        docker exec "$container" pg_dump -U postgres -Fc app | age -r "$(public_key)" >"$out.partial"
    )
    mv "$out.partial" "$out"
    find "$BACKUPS" -name 'app-*.dump.age' -mtime +"$KEEP_DAYS" -delete
    echo "backup: $out ($(du -h "$out" | cut -f1))"
}

counts() {
    local container=$1 database=$2 table
    for table in $LEARNER_TABLES; do
        printf '%s=%s ' "$table" "$(docker exec "$container" psql -U postgres -d "$database" -Atc "SELECT count(*) FROM $table")"
    done
}

# A backup is only a backup once it has been restored: the latest one, into a scratch database, compared.
restore_check() {
    local container latest live restored
    container=$(db_container)
    [[ -n $container ]] || fail "the database isn't running: ops/local/juku.sh start"
    latest=$(ls -t "$BACKUPS"/app-*.dump.age 2>/dev/null | head -1)
    [[ -n $latest ]] || fail "no backup in $BACKUPS yet: ops/local/juku.sh backup"
    docker exec -e PGOPTIONS="-c client_min_messages=warning" "$container" psql -U postgres -qc \
        "DROP DATABASE IF EXISTS restore_check" -c "CREATE DATABASE restore_check"
    age -d -i "$KEY" "$latest" | docker exec -i "$container" pg_restore -U postgres -d restore_check --no-owner
    live=$(counts "$container" app)
    restored=$(counts "$container" restore_check)
    docker exec "$container" psql -U postgres -qc "DROP DATABASE restore_check"
    echo "live:     $live"
    echo "restored: $restored ($(basename "$latest"))"
    [[ $live == "$restored" ]] || fail "the restored copy differs from the live database (a backup older than the last change?)"
    echo "restore check passed"
}

# The model calls run in a one-off container of the app's image, as on the server (ops/crontab). Skipped
# quietly while the stack is stopped: the next hour tries again.
weekly() {
    [[ -n $(db_container) ]] || { echo "weekly: the stack isn't running; skipped"; return 0; }
    "${COMPOSE[@]}" run --rm --no-deps -T app juku run-weekly --due
}

# launchd runs a missed job when the Mac wakes, unlike cron. The logs go next to the backups.
install_agent() {
    local name=$1 command=$2 schedule=$3 plist="$AGENTS_DIR/com.juku.$1.plist"
    mkdir -p "$BACKUPS"
    sed -e "s|@JUKU_SH@|$PWD/local/juku.sh|" -e "s|@LOG@|$BACKUPS/$name.log|" -e "s|@AGENT@|com.juku.$name|" \
        -e "s|@COMMAND@|$command|" -e "s|@SCHEDULE@|$schedule|" local/launch-agent.plist >"$plist"
    launchctl bootout "gui/$(id -u)/com.juku.$name" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$plist"
    echo "installed $plist: ops/local/juku.sh $command; log: $BACKUPS/$name.log"
}

install_schedule() {
    install_agent nightly-backup nightly "$NIGHTLY_AT"
    install_agent weekly-run weekly "$HOURLY"
}

case "${1:-}" in
start) start ;;
stop) "${COMPOSE[@]}" stop ;;
status) "${COMPOSE[@]}" ps --format '{{.Service}}: {{.State}} {{.Health}}' ;;
backup) backup ;;
restore-check) restore_check ;;
nightly) backup && restore_check ;;
weekly) weekly ;;
install-schedule) install_schedule ;;
compose) shift; "${COMPOSE[@]}" "$@" ;;
*) echo "usage: ops/local/juku.sh start|stop|status|backup|restore-check|nightly|weekly|install-schedule|compose ..." >&2; exit 2 ;;
esac
