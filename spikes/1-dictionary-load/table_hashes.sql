-- One content hash per dict table: two loads are identical when every row
-- of every table is. Run with psql -At.
SELECT format('SELECT %L, count(*), md5(string_agg(t::text, %L ORDER BY t::text)) FROM dict.%I t;',
              tablename, E'\n', tablename)
FROM pg_tables WHERE schemaname = 'dict' ORDER BY tablename
\gexec
