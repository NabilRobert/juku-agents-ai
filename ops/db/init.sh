#!/usr/bin/env bash
# Runs once, when the db container starts on an empty volume
# (/docker-entrypoint-initdb.d). Makes the two databases and the roles, and
# gives each login role its password from a secret file: the passwords are
# never in the repo or in the compose file.
set -euo pipefail

psql_admin() { psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --no-password "$@"; }

psql_admin --dbname postgres -f /juku/roles.sql

for role in juku_migrator juku_app juku_mcp juku_ops grafana_reader dict_owner; do
    secret="/run/secrets/${role}_password"
    if [[ ! -s "$secret" ]]; then
        echo "missing $secret: create it with ops/make-secrets.sh" >&2
        exit 1
    fi
    psql_admin --dbname postgres --set=role="$role" --set=password="$(cat "$secret")" <<'SQL'
ALTER ROLE :"role" LOGIN PASSWORD :'password';
SQL
done

psql_admin --dbname postgres <<'SQL'
CREATE DATABASE app OWNER juku_migrator;
CREATE DATABASE dict OWNER dict_owner;
REVOKE ALL ON DATABASE app FROM PUBLIC;
REVOKE ALL ON DATABASE dict FROM PUBLIC;
GRANT CONNECT ON DATABASE app TO juku_app, juku_mcp, juku_ops, grafana_reader;
GRANT CONNECT ON DATABASE dict TO dict_reader;
SQL

# Nobody but the owners may create objects in the public schemas.
psql_admin --dbname app -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC"
psql_admin --dbname dict -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC"
