-- Juku's database roles, one per job, each reaching only what it needs
-- (ADR-016, Phase 2 SM3). Run once per cluster as the superuser: by the
-- container's init script (ops/db/init.sh), and by the test fixtures.
-- Idempotent. Roles are made without a password here; init.sh sets LOGIN
-- and the password from secret files, so no password is ever in the repo.
--
--   juku_migrator   owns the app database's schemas; runs migrations and partition upkeep
--   juku_app        the web app: reads and writes learner data, writes per-call records
--   juku_mcp        Juku's MCP server: reads progress, memory and the dictionary; writes nothing
--   juku_ops        cron jobs: audit imports, heartbeats, job runs
--   grafana_reader  Grafana: reads the monitoring schema only
--   dict_owner      loads the dictionary database
--   dict_reader     a group: read-only on the dictionary (juku_mcp and MCP-backbone's login)
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'juku_migrator', 'juku_app', 'juku_mcp', 'juku_ops', 'grafana_reader', 'dict_owner', 'dict_reader'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', role_name);
        END IF;
    END LOOP;
END
$$;

GRANT dict_reader TO juku_mcp;

-- Spike 2: JIT compilation cost about 300 ms on the recommender's plan, so
-- it's off for the MCP server's queries (ADR-010, fitness function FF13).
ALTER ROLE juku_mcp SET jit = off;
-- A runaway query from an agent's tool can't hold the database for long.
ALTER ROLE juku_mcp SET statement_timeout = '2s';
ALTER ROLE juku_mcp SET default_transaction_read_only = on;
ALTER ROLE grafana_reader SET default_transaction_read_only = on;
ALTER ROLE dict_reader SET default_transaction_read_only = on;
