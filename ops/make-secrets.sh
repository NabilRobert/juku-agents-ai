#!/usr/bin/env bash
# Makes ops/secrets/: a fresh random password per database role, the
# database URLs built from them, the delegation signing key pair (Ed25519,
# ADR-018) and the session secret. Run once per server, by Arthur. It never
# overwrites a file that exists, so rerunning it is safe. The Telegram bot
# token is the one secret it can't make: put it in ops/secrets/telegram_bot_token.
set -euo pipefail
cd "$(dirname "$0")"
umask 077
mkdir -p secrets
cd secrets

make_secret() {  # name, command
    [[ -s "$1" ]] && return 0
    eval "$2" >"$1"
}

for role in postgres juku_migrator juku_app juku_mcp juku_ops grafana_reader dict_owner; do
    make_secret "${role}_password" "openssl rand -hex 24"
done
url() { printf 'postgresql+asyncpg://%s:%s@db:5432/%s' "$1" "$(cat "$1_password")" "$2"; }
make_secret juku_app_database_url "url juku_app app"
make_secret juku_ops_database_url "url juku_ops app"
make_secret juku_migrator_database_url "url juku_migrator app"
make_secret juku_mcp_app_database_url "url juku_mcp app"
make_secret juku_mcp_dict_database_url "url juku_mcp dict"
make_secret juku_session_secret "openssl rand -hex 32"
make_secret grafana_admin_password "openssl rand -hex 16"
if [[ ! -s juku_delegation_signing_key ]]; then
    openssl genpkey -algorithm ed25519 -out juku_delegation_signing_key
    openssl pkey -in juku_delegation_signing_key -pubout -out juku_mcp_delegation_public_key
fi
[[ -s telegram_bot_token ]] || echo "Now put the Telegram bot's token in ops/secrets/telegram_bot_token."
echo "ops/secrets/ is ready ($(ls | wc -l | tr -d ' ') files)."
