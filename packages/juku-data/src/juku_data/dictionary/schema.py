"""The dictionary's tables, keys, derived tables and views, as load.py builds them in the staging schema."""

BASE_TABLES_SQL = """
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
CREATE TABLE supplement_word (
    id text NOT NULL, word text NOT NULL, reading text NOT NULL, jmdict_id integer NOT NULL, meanings text NOT NULL);
CREATE TABLE sentence (
    sentence_id integer NOT NULL, ja text NOT NULL, furigana text, en text, tatoeba_id integer,
    content_words smallint NOT NULL);
CREATE TABLE sentence_word (sentence_id integer NOT NULL, word_id text NOT NULL);
CREATE TABLE sentence_breakdown (ja text NOT NULL, tokens jsonb NOT NULL, grammar_ids jsonb NOT NULL);
CREATE TABLE meta (
    openjlpt_commit text NOT NULL, sqlite_sha256 text NOT NULL, loaded_at timestamptz NOT NULL DEFAULT now(),
    sentences_total integer, content_tokens integer, content_tokens_mapped integer);
"""

KEYS_SQL = """
ALTER TABLE vocab ADD PRIMARY KEY (id);
ALTER TABLE vocab_example ADD PRIMARY KEY (vocab_id, ord);
ALTER TABLE vocab_example ADD FOREIGN KEY (vocab_id) REFERENCES vocab;
ALTER TABLE kanji ADD PRIMARY KEY (character);
ALTER TABLE grammar ADD PRIMARY KEY (id);
ALTER TABLE pos ADD PRIMARY KEY (code);
ALTER TABLE supplement_word ADD PRIMARY KEY (id);
ALTER TABLE sentence ADD PRIMARY KEY (sentence_id);
ALTER TABLE sentence_word ADD PRIMARY KEY (sentence_id, word_id);
ALTER TABLE sentence_breakdown ADD PRIMARY KEY (ja);
CREATE INDEX ON vocab (word);
CREATE INDEX ON vocab (reading);
CREATE INDEX ON vocab (jmdict_id);
CREATE INDEX ON vocab (level);
CREATE INDEX ON kanji (level);
CREATE INDEX ON grammar (level);
CREATE INDEX ON sentence_word (word_id);
CREATE INDEX ON sentence (content_words);
"""

# ADR-010's precomputed recommender tables, from spike 2 (precompute.sql, rewritten).
DERIVED_SQL = """
CREATE TABLE word_kanji AS
SELECT DISTINCT v.id, letter AS kanji
FROM vocab v, regexp_split_to_table(v.word, '') AS letter
WHERE EXISTS (SELECT 1 FROM kanji k WHERE k.character = letter);
ALTER TABLE word_kanji ADD PRIMARY KEY (id, kanji);
CREATE INDEX ON word_kanji (kanji);

CREATE TABLE word_level AS
SELECT v.id, v.word, v.reading, v.level,
       coalesce((SELECT max(coalesce(k.freq, 9999)) FROM word_kanji wk  -- no rank: the rarest
                 JOIN kanji k ON k.character = wk.kanji WHERE wk.id = v.id), 0)::smallint AS commonness
FROM vocab v;
ALTER TABLE word_level ADD PRIMARY KEY (id);

CREATE TABLE kanji_leverage AS
SELECT wk.kanji, levels.level::smallint AS level,
       count(*) FILTER (WHERE w.level >= levels.level)::integer AS words
FROM word_kanji wk JOIN word_level w USING (id) CROSS JOIN generate_series(1, 5) AS levels(level)
GROUP BY wk.kanji, levels.level;
ALTER TABLE kanji_leverage ADD PRIMARY KEY (kanji, level);
"""

# What each table is, for a model reading the schema through MCP-backbone (D4). Changing
# these is a tool-level change (Phase 1, F2), so they're versioned here, with the code.
TABLE_COMMENTS = {
    "vocab": "JLPT words from OpenJLPT. level: 5 = N5 (easiest) ... 1 = N1. meanings are English glosses.",
    "vocab_example": "Example sentences per word (from Tatoeba, CC BY 2.0 FR); furigana as {kanji|reading}.",
    "kanji": "JLPT kanji with readings, meanings, strokes and KANJIDIC2 frequency (freq: 1 = most frequent).",
    "grammar": "OpenJLPT's grammar points, N5-N1, with meaning, formation and examples.",
    "pos": "Part-of-speech codes used in vocab.pos (JMdict's).",
    "supplement_word": "Juku's reviewed supplement: common words in no JLPT list; they have no level.",
    "sentence": "Example sentences in which every content word maps to one word (reading practice).",
    "sentence_word": "Which words each reading-practice sentence contains.",
    "sentence_breakdown": (
        "Each example sentence (words' and grammar points'), as tokens {surface, reading, kind, word_ids} "
        "and the grammar point IDs it may use (matched by pattern, so some senses are possible, not certain)."
    ),
    "word_kanji": "The kanji in each word's spelling.",
    "word_level": "Each word's level and commonness (its rarest kanji's frequency rank; 0 = kana only).",
    "kanji_leverage": "How many words at or easier than `level` contain the kanji.",
    "meta": "Which OpenJLPT build this is, when it was loaded, and how much of the reading index mapped.",
    "words_overview": "One row per word: spelling, reading, level as N5..N1, English meanings joined by '; '.",
    "grammar_overview": "One row per grammar point, with its level as N5..N1.",
}

VIEWS_SQL = """
CREATE VIEW words_overview AS
SELECT v.id, v.word, v.reading, 'N' || v.level AS jlpt_level,
       (SELECT string_agg(meaning, '; ') FROM jsonb_array_elements_text(v.meanings) AS meaning) AS meanings,
       v.jmdict_id
FROM vocab v;
CREATE VIEW grammar_overview AS
SELECT g.id, g.pattern, g.reading, 'N' || g.level AS jlpt_level, g.meaning, g.formation
FROM grammar g;
"""
