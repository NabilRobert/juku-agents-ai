#!/usr/bin/env bash
# Spike 1: load JMdict, KANJIDIC2, KRADFILE and Tatoeba into a fresh database
# in a local postgres:16, and report row counts, disk size and load time.
#
# Usage: ./load.sh <database name>   (e.g. dict_a; it is dropped and recreated)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
RAW=$REPO/data/raw
DB=${1:?database name}
CONTAINER=juku-dict

# 1. The downloads must be the ones recorded.
(cd "$RAW" && shasum -a 256 -c "$HERE/checksums.sha256" --quiet) || { echo "checksum mismatch" >&2; exit 1; }

# 2. A local postgres:16, loopback only. Public dictionary data, so trust auth.
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
  docker run -d --name "$CONTAINER" -p 127.0.0.1:55437:5432 -e POSTGRES_HOST_AUTH_METHOD=trust \
    -v juku-dict-pgdata:/var/lib/postgresql/data postgres:16 >/dev/null
  until docker exec "$CONTAINER" pg_isready -U postgres -q; do sleep 1; done
  sleep 2
fi
psql() { docker exec -i "$CONTAINER" psql -U postgres -v ON_ERROR_STOP=1 -q "$@"; }

TSV=$(mktemp -d)
trap 'rm -rf "$TSV"' EXIT
t0=$(python3 -c 'import time; print(time.time())')

# 3. Parse (standard library only; untrusted input, so -I).
python3 -I "$HERE/parse.py" "$RAW" "$TSV" >/dev/null
t1=$(python3 -c 'import time; print(time.time())')

# 4. A fresh database: schema, COPY, then keys and indexes.
psql -d postgres -c "DROP DATABASE IF EXISTS $DB" -c "CREATE DATABASE $DB"
psql -d "$DB" <"$HERE/schema.sql"
for f in "$TSV"/*.tsv; do
  table=$(basename "$f" .tsv)
  psql -d "$DB" -c "\\copy dict.$table FROM STDIN" <"$f"
done
t2=$(python3 -c 'import time; print(time.time())')
psql -d "$DB" <"$HERE/indexes.sql"
t3=$(python3 -c 'import time; print(time.time())')

# 5. Report.
python3 -c "print(f'parse_s={$t1-$t0:.1f} copy_s={$t2-$t1:.1f} index_s={$t3-$t2:.1f} total_s={$t3-$t0:.1f}')"
psql -d "$DB" -At -F $'\t' <<'SQL'
SELECT 'version', source, version FROM dict.dict_version ORDER BY source;
SELECT 'database_bytes', pg_database_size(current_database()), pg_size_pretty(pg_database_size(current_database()));
SELECT 'dict_schema_bytes', sum(pg_total_relation_size(c.oid)), pg_size_pretty(sum(pg_total_relation_size(c.oid)))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'dict' AND c.relkind = 'r';
SELECT 'table', c.relname, c.reltuples::bigint, pg_size_pretty(pg_total_relation_size(c.oid))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'dict' AND c.relkind = 'r' ORDER BY pg_total_relation_size(c.oid) DESC;
SQL
psql -d "$DB" -At -F $'\t' <<'SQL'
SELECT 'index_lines_for_missing_sentences', count(DISTINCT line_no) FROM dict.tatoeba_index i
  WHERE NOT EXISTS (SELECT 1 FROM dict.tatoeba_sentence s WHERE s.id = i.sentence_id);
SELECT 'links_to_missing_sentences', count(*) FROM dict.tatoeba_link l
  WHERE NOT EXISTS (SELECT 1 FROM dict.tatoeba_sentence s WHERE s.id = l.jpn_id)
     OR NOT EXISTS (SELECT 1 FROM dict.tatoeba_sentence s WHERE s.id = l.ind_id);
SQL
# Exact counts, for comparing two loads.
psql -d "$DB" -At -F $'\t' -c "
  SELECT 'count', t, (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM dict.%I', t), false, true, '')))[1]::text
  FROM unnest(ARRAY(SELECT tablename::text FROM pg_tables WHERE schemaname = 'dict' ORDER BY 1)) AS t"
