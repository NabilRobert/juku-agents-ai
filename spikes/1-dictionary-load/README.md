# Spike 1: how big is the dictionary in Postgres, and how long does it take to load?

**Pass: 299 MB on disk, against the 1 GB limit, loaded in 18–23 s, with
identical content on a repeat load into a fresh container.**

```
./load.sh dict            # checksums, parse, COPY, keys and indexes, report
psql -At -f table_hashes.sql   # one count and md5 per table, to compare loads
```

- `parse.py` (standard library only) turns the downloads into COPY files.
  `test_parse.py` pins the COPY encoding and the index-token grammar
  (mutation-checked: dropping the empty-array NULL or the quote escaping
  fails a test).
- `schema.sql` creates bare tables in a `dict` schema; `indexes.sql` adds
  keys and lookups after the COPY.
- `checksums.sha256` records the downloads. `load.sh` refuses to run if
  they differ.

## The data (fetched 2026-10-28)

| Source | Version | Licence |
|---|---|---|
| JMdict_e (English glosses) | 2026-10-28 | EDRDG, CC BY-SA 4.0 |
| KANJIDIC2 | database version 2026-301 | EDRDG, CC BY-SA 4.0 |
| KRADFILE, KRADFILE2 | in kradzip.zip, files dated 2023-08-09 | EDRDG, CC BY-SA 4.0 |
| Tatoeba: Japanese and Indonesian sentences, jpn–ind links, Japanese word index | export of 2026-10-24 | CC BY 2.0 FR |

## Numbers

| Table | Rows | Size, with indexes |
|---|---|---|
| tatoeba_index | 1,178,440 | 122 MB |
| jmdict_gloss | 443,930 | 34 MB |
| jmdict_reading | 265,911 | 32 MB |
| tatoeba_sentence (248,941 jpn + 28,356 ind) | 277,297 | 31 MB |
| jmdict_sense | 253,882 | 29 MB |
| jmdict_kanji | 233,703 | 25 MB |
| jmdict_entry | 218,971 | 12 MB |
| kanjidic_char | 13,108 | 3 MB |
| kradfile | 12,156 | 1.7 MB |
| tatoeba_link (jpn–ind) | 6,262 | 0.7 MB |
| **The database** | | **299 MB** (`pg_database_size`) |

- The whole data directory is 576 MB, but 257 MB of that is WAL left by
  the bulk load (recycled up to `max_wal_size`), and the rest includes the
  template databases.
- **Load time:** 18.0 s on a fresh container (parse 9.5 s, COPY 3.3 s,
  keys and indexes 5.3 s); 18.5 s and 23.2 s on two other runs.
- **Row counts match the release:** entries, `k_ele`, `r_ele`, `sense` and
  `gloss` elements, characters, sentences, links and index tokens all equal
  a count of the source file.
- **Repeatable:** the container and its volume were deleted and the load
  run again; all 13 tables' md5 hashes are identical
  ([results-table-hashes.txt](results-table-hashes.txt)). The full report
  is [results-load.txt](results-load.txt).

## Found in the data (for slice 1)

- JMdict's DTD declares the entity `ik` twice, identically. The loader
  keeps the first, as XML does.
- Tatoeba's index has **105 (sentence, translation) pairs on more than one
  line** (some are wrong lines: sentence 208299 carries another sentence's
  index), so it's keyed by line number, not by sentence.
- **214 index lines name sentences Tatoeba has deleted,** and 2 links point
  at a missing sentence. No foreign key, then; slice 1 drops or reports
  them.
- 1 index token of 1,178,441 doesn't parse (`か如何か{かどうか}{かどう}`,
  two surface forms).
- Some index tokens carry a JMdict entry ID in place of a reading, as in
  `前(#1392580)[02]`. The loader stores it as `ent_seq` (spike 4 uses it).
- The XML is parsed with the standard library, not defusedxml, because
  JMdict needs its internal DTD entities. Expat 2.7.5 resolves no external
  entities and limits entity amplification.

## What it changes in the plan

Nothing. The scale path's "about 1 GB" for the dictionary can become
"about 0.3 GB, measured (spike 1)", and slice 1 inherits this loader.
