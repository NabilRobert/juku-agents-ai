-- Spike 4: the counts. Run after mapping.sql.
SET search_path = dict;
\pset footer off

\echo '== JLPT rows by level and how they were mapped'
SELECT level AS n, count(*) AS rows,
       count(*) FILTER (WHERE how = 'unique') AS unique,
       count(*) FILTER (WHERE how = 'R1') AS by_r1,
       count(*) FILTER (WHERE how = 'R2') AS by_r2,
       count(*) FILTER (WHERE how = 'R3') AS by_r3,
       count(*) FILTER (WHERE how = 'ambiguous') AS ambiguous,
       count(*) FILTER (WHERE how = 'unmatched') AS unmatched
FROM jlpt_map GROUP BY ROLLUP (level) ORDER BY level DESC NULLS LAST;

\echo '== Against the hand-added JMdict IDs (stephenmk): mapped rows that agree'
SELECT how, count(*) AS rows, count(*) FILTER (WHERE ent_seq = ref_seq) AS agree,
       round(100.0 * count(*) FILTER (WHERE ent_seq = ref_seq) / nullif(count(*), 0), 1) AS agree_pct
FROM jlpt_map WHERE ent_seq IS NOT NULL GROUP BY ROLLUP (how) ORDER BY how NULLS LAST;

\echo '== Hand-added IDs missing from this JMdict release (removed or merged entries)'
SELECT count(*) AS rows, count(DISTINCT ref_seq) AS ids FROM jlpt_list l
WHERE ref_seq IS NOT NULL AND NOT EXISTS (SELECT 1 FROM jmdict_entry e WHERE e.ent_seq = l.ref_seq);

\echo '== Ambiguous or unmatched rows whose hand-added ID is still valid (recoverable from the reference)'
SELECT how, count(*) AS rows FROM jlpt_map m
WHERE how IN ('ambiguous', 'unmatched') AND EXISTS (SELECT 1 FROM jmdict_entry e WHERE e.ent_seq = m.ref_seq)
GROUP BY how;

\echo '== Distinct entries per level, each at its easiest level (from the hand-added IDs)'
SELECT lvl AS n, count(*) AS entries FROM (
    SELECT ref_seq, max(level) AS lvl FROM jlpt_list l
    WHERE EXISTS (SELECT 1 FROM jmdict_entry e WHERE e.ent_seq = l.ref_seq) GROUP BY ref_seq) x
GROUP BY ROLLUP (lvl) ORDER BY lvl DESC NULLS LAST;

\echo '== Tatoeba: Japanese sentences indexed'
SELECT count(*) AS jpn_sentences,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM tatoeba_index i WHERE i.sentence_id = s.id)) AS indexed,
       round(100.0 * count(*) FILTER (WHERE EXISTS (SELECT 1 FROM tatoeba_index i WHERE i.sentence_id = s.id)) / count(*), 1) AS indexed_pct
FROM tatoeba_sentence s WHERE lang = 'jpn';

\echo '== Tatoeba index tokens (first index line per sentence) by how they were mapped'
SELECT how, count(*) AS tokens, round(100.0 * count(*) / (SELECT count(*) FROM index_token), 1) AS pct
FROM index_token JOIN token_map USING (key_id) GROUP BY ROLLUP (how) ORDER BY how NULLS LAST;

\echo '== Distinct token keys by how they were mapped'
SELECT how, count(*) AS keys FROM token_map GROUP BY ROLLUP (how) ORDER BY how NULLS LAST;

\echo '== Sentences whose every token maps to one entry (usable for i+1 reading practice)'
WITH per AS (SELECT sentence_id, bool_and(m.ent_seq IS NOT NULL) AS all_mapped
             FROM index_token JOIN token_map m USING (key_id) GROUP BY sentence_id)
SELECT count(*) AS indexed_sentences, count(*) FILTER (WHERE all_mapped) AS fully_mapped,
       round(100.0 * count(*) FILTER (WHERE all_mapped) / count(*), 1) AS fully_mapped_pct,
       round(100.0 * count(*) FILTER (WHERE all_mapped) / (SELECT count(*) FROM tatoeba_sentence WHERE lang = 'jpn'), 1)
           AS of_all_jpn_pct
FROM per;
