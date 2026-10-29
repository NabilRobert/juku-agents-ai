#!/usr/bin/env bash
# Sets up Juku on the managed database (ADR-016): the roles, their
# passwords, the two databases and their grants. Run by Arthur, once per
# cluster, from the repository, after ops/make-secrets.sh. Rerunning it is
# safe: it only adds what's missing and resets the passwords from the files.
#
# It connects with the provider's admin login, which may create roles and
# databases but needn't be a superuser. psql takes the connection from the
# usual libpq variables, and the password from ~/.pgpass or a prompt, so it
# never appears in a command line:
#
#   PGHOST=<the provider's host> PGUSER=<the admin login> ops/db/setup.sh
#
# TLS is required unless PGSSLMODE says otherwise.
set -euo pipefail
cd "$(dirname "$0")"
SECRETS=${JUKU_SECRETS_DIR:-../secrets}
export PGSSLMODE=${PGSSLMODE:-require}
export PGDATABASE=${PGDATABASE:-postgres}
: "${PGHOST:?set PGHOST to the provider's database host}"
: "${PGUSER:?set PGUSER to the provider's admin login}"

LOGIN_ROLES=(juku_migrator juku_app juku_mcp juku_ops grafana_reader dict_owner mcp_backbone)

admin() { psql -v ON_ERROR_STOP=1 --quiet --no-psqlrc "$@"; }

for role in "${LOGIN_ROLES[@]}"; do
    if [[ ! -s "$SECRETS/${role}_password" ]]; then
        echo "missing ops/secrets/${role}_password: run ops/make-secrets.sh first" >&2
        exit 1
    fi
done

admin -f roles.sql

# psql reads each password file itself (\set with backticks), so no
# password is ever on a command line where `ps` would show it.
for role in "${LOGIN_ROLES[@]}"; do
    admin --set=role="$role" <<SQL
\\set password \`cat '$SECRETS/${role}_password'\`
ALTER ROLE :"role" LOGIN PASSWORD :'password';
SQL
done

# A login that isn't a superuser may make a database owned by another role
# only if it can SET ROLE to it (Postgres 16), so the admin login joins the
# two owner roles first. It made them, so it may grant them to itself.
admin <<'SQL'
GRANT juku_migrator, dict_owner TO CURRENT_USER WITH INHERIT TRUE, SET TRUE;
SELECT 'CREATE DATABASE app OWNER juku_migrator'
    WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'app') \gexec
SELECT 'CREATE DATABASE dict OWNER dict_owner'
    WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'dict') \gexec
REVOKE ALL ON DATABASE app FROM PUBLIC;
REVOKE ALL ON DATABASE dict FROM PUBLIC;
GRANT CONNECT ON DATABASE app TO juku_app, juku_mcp, juku_ops, grafana_reader;
-- The nightly state check (FF3) and rebuilds compare through temporary tables.
GRANT TEMPORARY ON DATABASE app TO juku_app;
GRANT CONNECT ON DATABASE dict TO dict_reader;
SQL

# Nobody but the owners may create objects in the public schemas.
admin --dbname app -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC"
admin --dbname dict -c "REVOKE CREATE ON SCHEMA public FROM PUBLIC"
echo "Juku's roles and databases are ready on $PGHOST. Next: the migrations, then the dictionary load."
