-- Spike 1: keys and the lookups Juku needs (by spelling, by reading, by
-- sentence and by headword), built after the bulk load.
SET search_path = dict;

ALTER TABLE jmdict_kanji ADD PRIMARY KEY (ent_seq, ord);
ALTER TABLE jmdict_reading ADD PRIMARY KEY (ent_seq, ord);
ALTER TABLE jmdict_sense ADD PRIMARY KEY (ent_seq, ord);
ALTER TABLE jmdict_gloss ADD PRIMARY KEY (ent_seq, sense_ord, ord);
ALTER TABLE tatoeba_index ADD PRIMARY KEY (line_no, ord);
ALTER TABLE tatoeba_link ADD PRIMARY KEY (jpn_id, ind_id);

ALTER TABLE jmdict_kanji ADD FOREIGN KEY (ent_seq) REFERENCES jmdict_entry;
ALTER TABLE jmdict_reading ADD FOREIGN KEY (ent_seq) REFERENCES jmdict_entry;
ALTER TABLE jmdict_sense ADD FOREIGN KEY (ent_seq) REFERENCES jmdict_entry;
-- No foreign key from tatoeba_index to tatoeba_sentence: the index still lists
-- sentences Tatoeba has since deleted. load.sh counts them.

CREATE INDEX ON jmdict_kanji (keb);
CREATE INDEX ON jmdict_reading (reb);
CREATE INDEX ON tatoeba_index (headword, reading);
CREATE INDEX ON tatoeba_index (sentence_id);
CREATE INDEX ON tatoeba_link (ind_id);
CREATE INDEX ON kradfile (kanji);

ANALYZE;
