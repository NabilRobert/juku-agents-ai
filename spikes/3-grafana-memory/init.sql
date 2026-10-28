-- A tiny stand-in for Juku's monitoring schema (ADR-009), read by Grafana
-- through a read-only role.
CREATE SCHEMA monitoring;
CREATE TABLE monitoring.tool_calls (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at timestamptz NOT NULL,
    agent text NOT NULL,
    server text NOT NULL,
    tool text NOT NULL,
    ms integer NOT NULL,
    is_error boolean NOT NULL
);
INSERT INTO monitoring.tool_calls (at, agent, server, tool, ms, is_error)
SELECT now() - make_interval(mins => g),
       (ARRAY['shiori','keiko','nikki','tadashi'])[1 + g % 4],
       (ARRAY['juku','backbone'])[1 + g % 2],
       (ARRAY['get_progress','recommend_words','run_query','get_memory'])[1 + g % 4],
       20 + (g * 37) % 400,
       g % 23 = 0
FROM generate_series(1, 20000) AS g;
CREATE ROLE grafana_ro LOGIN;
GRANT USAGE ON SCHEMA monitoring TO grafana_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO grafana_ro;
