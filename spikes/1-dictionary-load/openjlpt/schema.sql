-- Spike 1 (OpenJLPT): OpenJLPT's tables in Postgres. JSON columns become
-- jsonb; levels become numbers (5 = N5 ... 1 = N1). Keys and indexes are
-- added after the COPY, in load.sh.
CREATE SCHEMA ojlpt;
SET search_path = ojlpt;

CREATE TABLE vocab (
    id text NOT NULL, word text NOT NULL, reading text NOT NULL, romaji text NOT NULL, meanings jsonb NOT NULL,
    level smallint NOT NULL, pos jsonb NOT NULL, jmdict_id integer, other_forms jsonb NOT NULL,
    other_readings jsonb NOT NULL, examples jsonb NOT NULL);
CREATE TABLE vocab_example (
    vocab_id text NOT NULL, ord smallint NOT NULL, ja text NOT NULL, furigana text, en text, tatoeba_id integer);
CREATE TABLE kanji (
    character text NOT NULL, level smallint NOT NULL, strokes smallint, grade smallint, freq smallint,
    radical text, radical_number smallint, onyomi jsonb NOT NULL, kunyomi jsonb NOT NULL, nanori jsonb NOT NULL,
    meanings jsonb NOT NULL, words jsonb NOT NULL, supplementary boolean NOT NULL);
CREATE TABLE grammar (
    id text NOT NULL, pattern text NOT NULL, reading text, romaji text NOT NULL, level smallint NOT NULL,
    meaning text NOT NULL, formation text NOT NULL, examples jsonb NOT NULL, tags jsonb NOT NULL, notes text);
CREATE TABLE pos (code text NOT NULL, description text NOT NULL);
