-- Spike 4: map the JLPT lists and Tatoeba's word index to JMdict entries by
-- spelling and reading, then settle ties with fixed rules, in order:
--   R1 priority: keep candidates whose matched spelling or reading carries a
--      JMdict priority tag (news1, ichi1, spec1, gai1, nfXX);
--   R2 primary form: keep candidates where the matched spelling (or, for a
--      kana word, the matched reading) is the entry's first;
--   R3 kana word: for a word written in kana, keep entries with no kanji
--      spelling or marked "usually kana" (uk) in their first sense.
-- Whatever is left with more than one candidate is ambiguous: it is reported
-- and left out, never guessed.
SET search_path = dict;

DROP TABLE IF EXISTS jlpt_list, jlpt_candidate, jlpt_map, index_line, token_key, index_token, token_candidate,
    token_map CASCADE;

CREATE TABLE jlpt_list (
    level smallint NOT NULL, line_no integer NOT NULL, ref_seq integer, kana text NOT NULL, kanji text,
    definition text, PRIMARY KEY (level, line_no));
\copy jlpt_list FROM '/tmp/jlpt.tsv'

CREATE FUNCTION pg_temp.is_kana(s text) RETURNS boolean IMMUTABLE LANGUAGE sql
    AS $$ SELECT s ~ '^[ぁ-ゖァ-ヺー・ゝゞヽヾ]+$' $$;

-- Features of one candidate entry for a (spelling, reading) pair.
CREATE FUNCTION pg_temp.features(seq integer, spelling text, reading text,
    OUT has_pri boolean, OUT is_primary boolean, OUT kana_pref boolean) STABLE LANGUAGE sql AS $$
    SELECT
        coalesce((SELECT bool_or(k.ke_pri IS NOT NULL) FROM jmdict_kanji k WHERE k.ent_seq = seq AND k.keb = spelling), false)
            OR coalesce((SELECT bool_or(r.re_pri IS NOT NULL) FROM jmdict_reading r
                         WHERE r.ent_seq = seq AND r.reb = coalesce(reading, spelling)), false),
        CASE WHEN pg_temp.is_kana(spelling)
             THEN EXISTS (SELECT 1 FROM jmdict_reading r WHERE r.ent_seq = seq AND r.ord = 1 AND r.reb = spelling)
             ELSE EXISTS (SELECT 1 FROM jmdict_kanji k WHERE k.ent_seq = seq AND k.ord = 1 AND k.keb = spelling) END,
        pg_temp.is_kana(spelling) AND (
            NOT EXISTS (SELECT 1 FROM jmdict_kanji k WHERE k.ent_seq = seq)
            OR EXISTS (SELECT 1 FROM jmdict_sense s WHERE s.ent_seq = seq AND s.ord = 1 AND 'uk' = ANY (s.misc)))
$$;

-- JLPT: a kanji word matches entries with that spelling and a reading valid
-- for it; a kana word matches entries with that reading.
CREATE TABLE jlpt_candidate AS
SELECT l.level, l.line_no, c.ent_seq, f.*
FROM jlpt_list l
CROSS JOIN LATERAL (
    SELECT DISTINCT k.ent_seq FROM jmdict_kanji k JOIN jmdict_reading r USING (ent_seq)
    WHERE l.kanji IS NOT NULL AND k.keb = l.kanji AND r.reb = l.kana
      AND NOT r.re_nokanji AND (r.re_restr IS NULL OR k.keb = ANY (r.re_restr))
    UNION
    SELECT DISTINCT r.ent_seq FROM jmdict_reading r WHERE l.kanji IS NULL AND r.reb = l.kana
) c
CROSS JOIN LATERAL pg_temp.features(c.ent_seq, coalesce(l.kanji, l.kana), l.kana) f;

-- Apply the rules in order. The stage is the first rule after which one
-- candidate is left (0 = it was unique to begin with).
CREATE FUNCTION pg_temp.resolve(tbl text, keys text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE format($q$
        CREATE TEMP TABLE resolved_%1$s AS
        WITH s0 AS (SELECT *, count(*) OVER w AS n0 FROM %1$s WINDOW w AS (PARTITION BY %2$s)),
        s1 AS (SELECT * FROM (SELECT *, bool_or(has_pri) OVER w AS m FROM s0 WINDOW w AS (PARTITION BY %2$s)) x
               WHERE has_pri OR NOT m),
        s1n AS (SELECT *, count(*) OVER w AS n1 FROM s1 WINDOW w AS (PARTITION BY %2$s)),
        s2 AS (SELECT * FROM (SELECT *, bool_or(is_primary) OVER w AS m2 FROM s1n WINDOW w AS (PARTITION BY %2$s)) x
               WHERE is_primary OR NOT m2),
        s2n AS (SELECT *, count(*) OVER w AS n2 FROM s2 WINDOW w AS (PARTITION BY %2$s)),
        s3 AS (SELECT * FROM (SELECT *, bool_or(kana_pref) OVER w AS m3 FROM s2n WINDOW w AS (PARTITION BY %2$s)) x
               WHERE kana_pref OR NOT m3),
        s3n AS (SELECT *, count(*) OVER w AS n3 FROM s3 WINDOW w AS (PARTITION BY %2$s))
        SELECT %2$s, ent_seq, n0, n1, n2, n3,
               CASE WHEN n0 = 1 THEN 'unique' WHEN n1 = 1 THEN 'R1' WHEN n2 = 1 THEN 'R2'
                    WHEN n3 = 1 THEN 'R3' ELSE 'ambiguous' END AS how
        FROM s3n $q$, tbl, keys);
END $$;

SELECT pg_temp.resolve('jlpt_candidate', 'level, line_no');

CREATE TABLE jlpt_map AS
SELECT l.level, l.line_no, l.ref_seq, l.kana, l.kanji,
       coalesce(min(r.how), 'unmatched') AS how,
       CASE WHEN count(r.ent_seq) = 1 THEN min(r.ent_seq) END AS ent_seq,
       count(r.ent_seq) AS left_candidates,
       coalesce(max(r.n0), 0) AS candidates
FROM jlpt_list l LEFT JOIN resolved_jlpt_candidate r USING (level, line_no)
GROUP BY 1, 2, 3, 4, 5;

-- Tatoeba: one index line per existing Japanese sentence (the first), and
-- each distinct token key mapped once.
CREATE TABLE index_line AS
SELECT DISTINCT ON (i.sentence_id) i.sentence_id, i.line_no
FROM tatoeba_index i JOIN tatoeba_sentence s ON s.id = i.sentence_id AND s.lang = 'jpn'
ORDER BY i.sentence_id, i.line_no;

CREATE TABLE token_key AS
SELECT DISTINCT i.headword, i.reading, i.ent_seq AS given_seq
FROM tatoeba_index i JOIN index_line USING (line_no);
ALTER TABLE token_key ADD COLUMN key_id serial PRIMARY KEY;

-- Each token of those lines, with its key (NULLs made comparable, so this is
-- a hash join rather than a nested loop over 1.2 million tokens).
CREATE TABLE index_token AS
SELECT l.sentence_id, i.line_no, i.ord, t.key_id
FROM index_line l JOIN tatoeba_index i USING (line_no)
JOIN token_key t ON t.headword = i.headword AND coalesce(t.reading, '∅') = coalesce(i.reading, '∅')
                AND coalesce(t.given_seq, -1) = coalesce(i.ent_seq, -1);

CREATE TABLE token_candidate AS
SELECT t.key_id, c.ent_seq, f.*
FROM token_key t
CROSS JOIN LATERAL (
    SELECT e.ent_seq FROM jmdict_entry e WHERE e.ent_seq = t.given_seq
    UNION
    SELECT k.ent_seq FROM jmdict_kanji k
    WHERE t.given_seq IS NULL AND NOT pg_temp.is_kana(t.headword) AND k.keb = t.headword
      AND (t.reading IS NULL OR EXISTS (SELECT 1 FROM jmdict_reading r WHERE r.ent_seq = k.ent_seq AND r.reb = t.reading))
    UNION
    SELECT r.ent_seq FROM jmdict_reading r
    WHERE t.given_seq IS NULL AND pg_temp.is_kana(t.headword) AND r.reb = t.headword
) c
CROSS JOIN LATERAL pg_temp.features(c.ent_seq, t.headword, t.reading) f;

SELECT pg_temp.resolve('token_candidate', 'key_id');

CREATE TABLE token_map AS
SELECT t.key_id, t.headword, t.reading, t.given_seq,
       CASE WHEN t.given_seq IS NOT NULL AND count(r.ent_seq) = 1 THEN 'given_id'
            ELSE coalesce(min(r.how), 'unmatched') END AS how,
       CASE WHEN count(r.ent_seq) = 1 THEN min(r.ent_seq) END AS ent_seq
FROM token_key t LEFT JOIN resolved_token_candidate r USING (key_id)
GROUP BY 1, 2, 3, 4;
