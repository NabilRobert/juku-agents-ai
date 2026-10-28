-- Spike 2: the recommender's precomputed tables (ADR-010), built from
-- spike 1's dictionary and spike 4's mapping. Levels are numbers: 5 = N5
-- (easiest) ... 1 = N1, so "easier" means a larger number.
SET search_path = dict;
DROP TABLE IF EXISTS word_level, word_kanji, kanji_level, kanji_leverage, sentence_word, sentence_size CASCADE;

-- One row per mapped JLPT entry, at its easiest level.
CREATE TABLE word_level AS
SELECT m.ent_seq,
       max(m.level)::smallint AS level,
       -- tier: common if any form has a priority tag
       bool_or(EXISTS (SELECT 1 FROM jmdict_kanji k WHERE k.ent_seq = m.ent_seq AND k.ke_pri IS NOT NULL)
            OR EXISTS (SELECT 1 FROM jmdict_reading r WHERE r.ent_seq = m.ent_seq AND r.re_pri IS NOT NULL)) AS common,
       -- frequency band: the best nfXX tag (1-48, 500 words each), 99 when there is none
       coalesce((SELECT min(substr(p, 3)::smallint) FROM (
                    SELECT unnest(ke_pri) p FROM jmdict_kanji k WHERE k.ent_seq = m.ent_seq
                    UNION ALL SELECT unnest(re_pri) FROM jmdict_reading r WHERE r.ent_seq = m.ent_seq) x
                 WHERE p LIKE 'nf%'), 99)::smallint AS freq_band,
       -- what the learner sees: the first spelling, else the first reading
       coalesce((SELECT keb FROM jmdict_kanji k WHERE k.ent_seq = m.ent_seq ORDER BY ord LIMIT 1),
                (SELECT reb FROM jmdict_reading r WHERE r.ent_seq = m.ent_seq ORDER BY ord LIMIT 1)) AS written,
       (SELECT reb FROM jmdict_reading r WHERE r.ent_seq = m.ent_seq ORDER BY ord LIMIT 1) AS reading
FROM jlpt_map m WHERE m.ent_seq IS NOT NULL
GROUP BY m.ent_seq;
ALTER TABLE word_level ADD PRIMARY KEY (ent_seq);

-- The kanji in each word's first spelling.
CREATE TABLE word_kanji AS
SELECT DISTINCT w.ent_seq, ch AS kanji
FROM word_level w, regexp_split_to_table(w.written, '') AS ch
WHERE EXISTS (SELECT 1 FROM kanjidic_char c WHERE c.literal = ch);
ALTER TABLE word_kanji ADD PRIMARY KEY (ent_seq, kanji);
CREATE INDEX ON word_kanji (kanji);

-- A kanji's level: the easiest level of a listed word that contains it.
CREATE TABLE kanji_level AS
SELECT wk.kanji, max(w.level)::smallint AS level
FROM word_kanji wk JOIN word_level w USING (ent_seq) GROUP BY wk.kanji;
ALTER TABLE kanji_level ADD PRIMARY KEY (kanji);

-- Leverage: how many common words at or below (easier than or equal to)
-- each level contain the kanji.
CREATE TABLE kanji_leverage AS
SELECT wk.kanji, lv.level::smallint AS level,
       count(*) FILTER (WHERE w.common AND w.level >= lv.level)::integer AS common_words
FROM word_kanji wk JOIN word_level w USING (ent_seq) CROSS JOIN generate_series(1, 5) AS lv(level)
GROUP BY wk.kanji, lv.level;
ALTER TABLE kanji_leverage ADD PRIMARY KEY (kanji, level);

-- Reading practice: the distinct entries in each fully mapped sentence (spike 4).
CREATE TABLE sentence_word AS
SELECT DISTINCT it.sentence_id, tm.ent_seq
FROM index_token it JOIN token_map tm USING (key_id)
WHERE it.sentence_id IN (SELECT sentence_id FROM index_token JOIN token_map USING (key_id)
                         GROUP BY sentence_id HAVING bool_and(ent_seq IS NOT NULL));
ALTER TABLE sentence_word ADD PRIMARY KEY (sentence_id, ent_seq);
CREATE INDEX ON sentence_word (ent_seq);

-- Each sentence's count of content words: function words (particles,
-- copula, auxiliaries, conjunctions) are taken as known, so they don't count.
CREATE TABLE sentence_size AS
SELECT sw.sentence_id, count(*) FILTER (WHERE NOT fw.is_function)::smallint AS content_words
FROM sentence_word sw
CROSS JOIN LATERAL (SELECT EXISTS (
    SELECT 1 FROM jmdict_sense s WHERE s.ent_seq = sw.ent_seq AND s.ord = 1
      AND s.pos && ARRAY['prt', 'cop', 'aux', 'aux-v', 'aux-adj', 'conj'])) AS fw(is_function)
GROUP BY sw.sentence_id;
ALTER TABLE sentence_size ADD PRIMARY KEY (sentence_id);
CREATE INDEX ON sentence_size (content_words);

-- Keep only content words in sentence_word, so a query counts unknowns directly.
DELETE FROM sentence_word sw WHERE EXISTS (
    SELECT 1 FROM jmdict_sense s WHERE s.ent_seq = sw.ent_seq AND s.ord = 1
      AND s.pos && ARRAY['prt', 'cop', 'aux', 'aux-v', 'aux-adj', 'conj']);

ANALYZE word_level, word_kanji, kanji_level, kanji_leverage, sentence_word, sentence_size;

SELECT 'word_level', count(*) FROM word_level
UNION ALL SELECT 'word_kanji', count(*) FROM word_kanji
UNION ALL SELECT 'kanji_level', count(*) FROM kanji_level
UNION ALL SELECT 'kanji_leverage', count(*) FROM kanji_leverage
UNION ALL SELECT 'sentence_word (content words)', count(*) FROM sentence_word
UNION ALL SELECT 'sentence_size', count(*) FROM sentence_size;
