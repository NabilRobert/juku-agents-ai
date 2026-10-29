-- Spike 1: the dictionary database, as loaded from the official releases.
-- Tables are created bare; indexes come after the COPY (load.sh), which is
-- the fast order for a bulk load.
CREATE SCHEMA dict;
SET search_path = dict;

CREATE TABLE dict_version (source text PRIMARY KEY, version text);

CREATE TABLE jmdict_entity (code text PRIMARY KEY, description text NOT NULL);
CREATE TABLE jmdict_entry (ent_seq integer PRIMARY KEY);
CREATE TABLE jmdict_kanji (
    ent_seq integer NOT NULL, ord smallint NOT NULL, keb text NOT NULL,
    ke_inf text[], ke_pri text[]);
CREATE TABLE jmdict_reading (
    ent_seq integer NOT NULL, ord smallint NOT NULL, reb text NOT NULL,
    re_nokanji boolean NOT NULL, re_restr text[], re_inf text[], re_pri text[]);
CREATE TABLE jmdict_sense (
    ent_seq integer NOT NULL, ord smallint NOT NULL, pos text[], field text[], misc text[],
    dial text[], stagk text[], stagr text[], xref text[], s_inf text[]);
CREATE TABLE jmdict_gloss (
    ent_seq integer NOT NULL, sense_ord smallint NOT NULL, ord smallint NOT NULL,
    gloss text NOT NULL, g_type text);

CREATE TABLE kanjidic_char (
    literal text PRIMARY KEY, grade smallint, stroke_count smallint, freq smallint,
    jlpt_old smallint, radical smallint, on_readings text[], kun_readings text[],
    meanings_en text[], nanori text[]);
CREATE TABLE kradfile (kanji text NOT NULL, components text[] NOT NULL, source text NOT NULL);

CREATE TABLE tatoeba_sentence (id integer PRIMARY KEY, lang text NOT NULL, text text NOT NULL);
CREATE TABLE tatoeba_link (jpn_id integer NOT NULL, ind_id integer NOT NULL);
CREATE TABLE tatoeba_index (
    line_no integer NOT NULL, sentence_id integer NOT NULL, meaning_id integer NOT NULL, ord smallint NOT NULL,
    headword text NOT NULL, reading text, ent_seq integer, sense_no smallint, surface text, checked boolean NOT NULL);
CREATE TABLE tatoeba_index_unparsed (
    line_no integer NOT NULL, sentence_id integer NOT NULL, ord smallint NOT NULL, token text NOT NULL);
