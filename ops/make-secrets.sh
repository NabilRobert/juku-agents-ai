#!/usr/bin/env bash
# Makes ops/secrets/: a fresh random password per database login, the
# database URLs built from them, the delegation signing key pair (Ed25519,
# ADR-018) and the session secret. Run once per server, by Arthur, before
# ops/db/setup.sh gives the logins these passwords. It never overwrites a
# file that exists, so rerunning it is safe. Four secrets come from
# elsewhere and are put in ops/secrets/ by hand: the Telegram bot's token,
# Shiori's and Keiko's gateway keys (from the gateway's deployment) and the
# Sumopod key (the capped key of slice plan P3). The provider's admin
# password is never here: setup.sh asks for it.
#
# The database's host and port come from ops/.env (JUKU_DB_HOST, JUKU_DB_PORT).
# Every URL requires TLS.
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${JUKU_DB_HOST:-}" && -f .env ]]; then
    JUKU_DB_HOST=$(sed -n 's/^JUKU_DB_HOST=//p' .env)
    JUKU_DB_PORT=${JUKU_DB_PORT:-$(sed -n 's/^JUKU_DB_PORT=//p' .env)}
fi
if [[ -z "${JUKU_DB_HOST:-}" ]]; then
    echo "JUKU_DB_HOST is not set: add the database's host to ops/.env (see ops/.env.example)" >&2
    exit 1
fi
JUKU_DB_PORT=${JUKU_DB_PORT:-5432}
umask 077
mkdir -p secrets
cd secrets

make_secret() {  # name, command
    [[ -s "$1" ]] && return 0
    eval "$2" >"$1"
}

for role in juku_migrator juku_app juku_mcp juku_ops grafana_reader dict_owner mcp_backbone; do
    make_secret "${role}_password" "openssl rand -hex 24"
done
# SQLAlchemy's asyncpg URLs take ssl=require; libpq's (MCP-backbone's) take sslmode=require.
url() {
    printf 'postgresql+asyncpg://%s:%s@%s:%s/%s?ssl=require' \
        "$1" "$(cat "$1_password")" "$JUKU_DB_HOST" "$JUKU_DB_PORT" "$2"
}
libpq_url() {
    printf 'postgresql://%s:%s@%s:%s/%s?sslmode=require' \
        "$1" "$(cat "$1_password")" "$JUKU_DB_HOST" "$JUKU_DB_PORT" "$2"
}
make_secret juku_app_database_url "url juku_app app"
make_secret juku_ops_database_url "url juku_ops app"
make_secret juku_migrator_database_url "url juku_migrator app"
make_secret juku_mcp_app_database_url "url juku_mcp app"
make_secret juku_mcp_dict_database_url "url juku_mcp dict"
make_secret juku_dict_database_url "url juku_app dict"
make_secret juku_dict_owner_database_url "url dict_owner dict"
# For MCP-backbone's own deployment; Juku's containers don't mount it.
make_secret mcp_backbone_dict_database_url "libpq_url mcp_backbone dict"
make_secret juku_session_secret "openssl rand -hex 32"
make_secret grafana_admin_password "openssl rand -hex 16"
if [[ ! -s juku_delegation_signing_key ]]; then
    openssl genpkey -algorithm ed25519 -out juku_delegation_signing_key
    openssl pkey -in juku_delegation_signing_key -pubout -out juku_mcp_delegation_public_key
fi
for given in telegram_bot_token juku_shiori_gateway_key juku_keiko_gateway_key juku_model_api_key; do
    [[ -s $given ]] || echo "Still to add by hand: ops/secrets/$given"
done
echo "ops/secrets/ is ready ($(ls | wc -l | tr -d ' ') files)."
