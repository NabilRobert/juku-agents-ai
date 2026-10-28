#!/usr/bin/env bash
# Spike 1 (OpenJLPT): load a pinned OpenJLPT SQLite into a fresh database in
# the local postgres:16 (container juku-dict, from ../load.sh), and report row
# counts, disk size, load time and one md5 per table.
#
# Usage: ./load.sh <database name>   (dropped and recreated)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=$(cd "$HERE/../../.." && pwd)/data/raw/openjlpt-main
DB=${1:?database name}
(cd "$RAW" && shasum -a 256 -c "$HERE/checksums.sha256" --quiet) || { echo "checksum mismatch" >&2; exit 1; }
psql() { docker exec -i juku-dict psql -U postgres -v ON_ERROR_STOP=1 -q "$@"; }
now() { python3 -c 'import time; print(time.time())'; }

TSV=$(mktemp -d)
trap 'rm -rf "$TSV"' EXIT
t0=$(now)
python3 -I "$HERE/sqlite_to_tsv.py" "$RAW/openjlpt.sqlite" "$TSV" >/dev/null
t1=$(now)
psql -d postgres -c "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB"
psql -d "$DB" <"$HERE/schema.sql"
for f in "$TSV"/*.tsv; do psql -d "$DB" -c "\\copy ojlpt.$(basename "$f" .tsv) FROM STDIN" <"$f"; done
t2=$(now)
psql -d "$DB" <<'SQL'
SET search_path = ojlpt;
ALTER TABLE vocab ADD PRIMARY KEY (id);
ALTER TABLE vocab_example ADD PRIMARY KEY (vocab_id, ord);
ALTER TABLE vocab_example ADD FOREIGN KEY (vocab_id) REFERENCES vocab;
ALTER TABLE kanji ADD PRIMARY KEY (character);
ALTER TABLE grammar ADD PRIMARY KEY (id);
ALTER TABLE pos ADD PRIMARY KEY (code);
CREATE INDEX ON vocab (word);
CREATE INDEX ON vocab (reading);
CREATE INDEX ON vocab (jmdict_id);
CREATE INDEX ON vocab (level);
CREATE INDEX ON kanji (level);
CREATE INDEX ON grammar (level);
ANALYZE;
SQL
t3=$(now)
python3 -c "print(f'convert_s={$t1-$t0:.2f} copy_s={$t2-$t1:.2f} index_s={$t3-$t2:.2f} total_s={$t3-$t0:.2f}')"
psql -d "$DB" -At -F $'\t' <<'SQL'
SELECT 'database_bytes', pg_database_size(current_database()), pg_size_pretty(pg_database_size(current_database()));
SELECT 'ojlpt_schema_bytes', sum(pg_total_relation_size(c.oid)), pg_size_pretty(sum(pg_total_relation_size(c.oid)))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'ojlpt' AND c.relkind = 'r';
SELECT 'table', c.relname, pg_size_pretty(pg_total_relation_size(c.oid))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'ojlpt' AND c.relkind = 'r' ORDER BY pg_total_relation_size(c.oid) DESC;
SELECT format('SELECT %L, ''hash'', count(*), md5(string_agg(t::text, E''\n'' ORDER BY t::text)) FROM ojlpt.%I t;',
              tablename, tablename)
FROM pg_tables WHERE schemaname = 'ojlpt' ORDER BY tablename
\gexec
SQL
