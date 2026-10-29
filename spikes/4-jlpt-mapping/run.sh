#!/usr/bin/env bash
# Spike 4: load the JLPT lists, map them and Tatoeba's index to JMdict, and
# report. Needs spike 1's database. Usage: ./run.sh <database> > results.txt
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=$(cd "$HERE/../.." && pwd)/data/raw
DB=${1:-dict}
TSV=$(mktemp)
trap 'rm -f "$TSV"' EXIT
python3 -I "$HERE/jlpt_tsv.py" "$RAW/jlpt" >"$TSV"
docker cp -q "$TSV" juku-dict:/tmp/jlpt.tsv
psql() { docker exec -i juku-dict psql -U postgres -d "$DB" -v ON_ERROR_STOP=1 -q "$@"; }
start=$(date +%s)
psql <"$HERE/mapping.sql"
echo "mapping_s=$(($(date +%s) - start))"
psql <"$HERE/report.sql"
