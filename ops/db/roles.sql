-- Juku's database roles, one per job, each reaching only what it needs
-- (ADR-016, Phase 2 SM3). Run once per cluster with a login that may
-- create roles: by ops/db/setup.sh, as the provider's admin login, and by
-- the test fixtures, as the test server's superuser. Idempotent. Roles are
-- made without a password here; setup.sh sets LOGIN and the password from
-- secret files, so no password is ever in the repo.
--
--   juku_migrator   owns the app database's schemas; runs migrations and partition upkeep
--   juku_app        the web app: reads and writes learner data, writes per-call records
--   juku_mcp        Juku's MCP server: reads progress, memory and the dictionary; writes nothing
--   juku_ops        cron jobs: audit imports, heartbeats, job runs
--   grafana_reader  Grafana: reads the monitoring schema only
--   dict_owner      loads the dictionary database
--   mcp_backbone    MCP-backbone's login: the dictionary, read-only
--   dict_reader     a group: read-only on the dictionary (juku_mcp, juku_app and mcp_backbone)
DO $$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'juku_migrator', 'juku_app', 'juku_mcp', 'juku_ops', 'grafana_reader', 'dict_owner', 'dict_reader',
        'mcp_backbone'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', role_name);
        END IF;
    END LOOP;
END
$$;

-- The MCP server and the app read the dictionary (the app for quizzes and
-- word details), and so does MCP-backbone.
GRANT dict_reader TO juku_mcp, juku_app, mcp_backbone;

-- Spike 2: JIT compilation cost about 300 ms on the recommender's plan, so
-- it's off for the MCP server's queries (ADR-010, fitness function FF13).
ALTER ROLE juku_mcp SET jit = off;
-- A runaway query from an agent's tool can't hold the database for long.
ALTER ROLE juku_mcp SET statement_timeout = '2s';
ALTER ROLE juku_mcp SET default_transaction_read_only = on;
ALTER ROLE grafana_reader SET default_transaction_read_only = on;
ALTER ROLE dict_reader SET default_transaction_read_only = on;
-- A group's settings don't reach its members' sessions, so each reader has its own.
ALTER ROLE mcp_backbone SET default_transaction_read_only = on;

-- Each login's share of the provider's connections: guardrails.yaml's
-- `database` section, which a test keeps equal to these (juku_app's is its
-- two pools plus two for a hand-run command or the nightly check, one per database).
ALTER ROLE juku_app CONNECTION LIMIT 7;
ALTER ROLE juku_mcp CONNECTION LIMIT 4;
ALTER ROLE juku_ops CONNECTION LIMIT 3;
ALTER ROLE juku_migrator CONNECTION LIMIT 1;
ALTER ROLE dict_owner CONNECTION LIMIT 1;
ALTER ROLE grafana_reader CONNECTION LIMIT 2;
ALTER ROLE mcp_backbone CONNECTION LIMIT 1;
