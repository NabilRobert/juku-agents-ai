-- Spike 2 (OpenJLPT): ADR-010's tables as rewritten for OpenJLPT, in the
-- `openjlpt` database from spike 1. Levels: 5 = N5 ... 1 = N1.
SET search_path = ojlpt;
DROP TABLE IF EXISTS word_level, word_kanji, kanji_leverage CASCADE;

-- The kanji in each word's spelling (those OpenJLPT lists).
CREATE TABLE word_kanji AS
SELECT DISTINCT v.id, ch AS kanji
FROM vocab v, regexp_split_to_table(v.word, '') AS ch
WHERE EXISTS (SELECT 1 FROM kanji k WHERE k.character = ch);
ALTER TABLE word_kanji ADD PRIMARY KEY (id, kanji);
CREATE INDEX ON word_kanji (kanji);

-- Level, plus commonness: the KANJIDIC2 frequency rank of the word's rarest
-- kanji (a larger rank is rarer; a kanji with no rank counts as rarest,
-- 9999). Kana-only words count as common (0).
CREATE TABLE word_level AS
SELECT v.id, v.word, v.reading, v.level,
       coalesce((SELECT max(coalesce(k.freq, 9999)) FROM word_kanji wk JOIN kanji k ON k.character = wk.kanji
                 WHERE wk.id = v.id), 0)::smallint AS commonness
FROM vocab v;
ALTER TABLE word_level ADD PRIMARY KEY (id);

-- Leverage: how many words at or below (easier than or equal to) each level
-- contain the kanji.
CREATE TABLE kanji_leverage AS
SELECT wk.kanji, lv.level::smallint AS level, count(*) FILTER (WHERE w.level >= lv.level)::integer AS words
FROM word_kanji wk JOIN word_level w USING (id) CROSS JOIN generate_series(1, 5) AS lv(level)
GROUP BY wk.kanji, lv.level;
ALTER TABLE kanji_leverage ADD PRIMARY KEY (kanji, level);

ANALYZE word_kanji, word_level, kanji_leverage;
SELECT 'word_level', count(*) FROM word_level
UNION ALL SELECT 'word_kanji', count(*) FROM word_kanji
UNION ALL SELECT 'kanji_leverage', count(*) FROM kanji_leverage;
