#!/usr/bin/env bash
# Spike 4 (OpenJLPT): compare OpenJLPT's words with Waller's lists as mapped
# by this spike (dict.jlpt_list, dict.jlpt_map). Usage: ./compare.sh > results-compare.txt
set -euo pipefail
RAW=$(cd "$(dirname "$0")/../../.." && pwd)/data/raw/openjlpt-main
TSV=$(mktemp)
trap 'rm -f "$TSV"' EXIT
sqlite3 -readonly -separator $'\t' "$RAW/openjlpt.sqlite" "SELECT id, word, reading, jmdict_id, level FROM vocab" >"$TSV"
docker cp -q "$TSV" juku-dict:/tmp/oj_vocab.tsv
docker exec -i juku-dict psql -U postgres -d dict -q -v ON_ERROR_STOP=1 <<'SQL'
SET search_path = dict;
DROP TABLE IF EXISTS oj_vocab;
CREATE TABLE oj_vocab (id text, word text, reading text, jmdict_id integer, level text);
\copy oj_vocab FROM '/tmp/oj_vocab.tsv' WITH (NULL '')
\echo '== Waller rows whose reference JMdict ID no OpenJLPT word carries, by level'
SELECT l.level, count(*) AS rows, count(DISTINCT l.ref_seq) AS entries
FROM jlpt_list l WHERE l.ref_seq IS NOT NULL AND NOT EXISTS (SELECT 1 FROM oj_vocab o WHERE o.jmdict_id = l.ref_seq)
GROUP BY ROLLUP (l.level) ORDER BY 1 DESC NULLS LAST;
\echo '== Those rows at N5-N3'
SELECT l.level, string_agg(coalesce(l.kanji, l.kana), ' ' ORDER BY l.line_no) FROM jlpt_list l
WHERE l.level >= 3 AND l.ref_seq IS NOT NULL AND NOT EXISTS (SELECT 1 FROM oj_vocab o WHERE o.jmdict_id = l.ref_seq)
GROUP BY 1 ORDER BY 1 DESC;
\echo '== OpenJLPT words whose JMdict ID is in no Waller row, by level'
SELECT o.level, count(*) FROM oj_vocab o
WHERE o.jmdict_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM jlpt_list l WHERE l.ref_seq = o.jmdict_id) GROUP BY 1 ORDER BY 1;
\echo '== The same entry at OpenJLPT''s level vs its easiest Waller level'
WITH w AS (SELECT ref_seq, max(level) AS lvl FROM jlpt_list WHERE ref_seq IS NOT NULL GROUP BY 1)
SELECT count(*) FILTER (WHERE ('N' || w.lvl) = o.level) AS same_level, count(*) FILTER (WHERE ('N' || w.lvl) <> o.level) AS different
FROM oj_vocab o JOIN w ON w.ref_seq = o.jmdict_id;
\echo '== Are 父, 母, 顔 in either list?'
SELECT 'waller' AS list, count(*) FROM jlpt_list WHERE coalesce(kanji, kana) IN ('父', '母', '顔')
UNION ALL SELECT 'openjlpt', count(*) FROM oj_vocab WHERE word IN ('父', '母', '顔');
SQL
