# Spike 2: do the recommender and i+1 queries fit the limits?

**Pass, after one fix.** Through the MCP server prototype, with 0, 100 and
500 known words at N5–N2, the rewritten recommender takes 4–21 ms (p50) and
at most 69 ms. The i+1 sentence query takes 3–72 ms (p50) and at most
120 ms. The first version of the recommender failed (about 220 ms p50, up
to 722 ms), almost all of it Postgres JIT compilation, not the query.

```
psql -d dict -f precompute.sql     # ADR-010's tables, from spikes 1 and 4 (about 5 s)
python bench.py v2 on > results-v2-jit-on.md   # v1|v2, jit on|off
python grow.py > results-growth.md             # 500 to 4,000 known words
```

- `server.py` is a minimal Juku MCP server (`MCPServer`, mcp 2.3.0) with
  `recommend_words(level)` and `find_reading_sentences()`. No tool takes a
  learner ID; the learner is fixed at build time here (spike 6 binds it to
  a token).
- The learner's known words are read from an `app` database, and the
  dictionary is a separate database, so the known words go to the
  dictionary query as an `int[]`. Postgres can't join across databases.
  Both reads are inside the timings.
- `app.learner_word` holds the three fixture learners, plus 5,000
  synthetic ones (2.1 million rows), so the known-words read isn't flattered
  by an empty table.
- The results files quote a few sample sentences from Tatoeba (CC BY 2.0 FR,
  tatoeba.org) and words from JMdict (EDRDG, CC BY-SA 4.0).
- Each cell is 50 timed calls after 5 warm-ups, measured at the MCP client
  (in memory, so no network), on Arthur's laptop with Postgres 16 in
  Docker.

## Built from ADR-010

`precompute.sql` makes `word_level` (7,723 entries: easiest level, common
tier, nf frequency band), `word_kanji` (11,706), `kanji_level` (2,108
kanji, each at the easiest level of a listed word containing it),
`kanji_leverage` (common words at or below each level containing the
kanji), and, for reading practice, `sentence_word` and `sentence_size` over
the 102,568 fully mapped sentences of spike 4. The query follows ADR-010's
rules exactly: the candidates, the five-key lexicographic order, at most 3
of 10 sharing a new kanji, and a reason built from the row, for example
"1 kanji baru: 何, muncul di 13 kata umum N5."

## Numbers (round trip at the MCP client, ms: p50 / p95 / max)

**v2, the rewritten recommender, jit on** ([results-v2-jit-on.md](results-v2-jit-on.md)):

| Level | 0 known | 100 known | 500 known |
|---|---|---|---|
| `recommend_words` N5 | 4.2 / 5.0 / 5.6 | 4.8 / 6.6 / 7.4 | 5.0 / 6.2 / 7.1 |
| `recommend_words` N4 | 7.4 / 7.8 / 8.9 | 7.3 / 7.9 / 17.0 | 7.7 / 13.5 / 69.4 |
| `recommend_words` N3 | 10.6 / 14.6 / 23.9 | 10.9 / 20.6 / 62.0 | 11.0 / 13.9 / 49.9 |
| `recommend_words` N2 | 13.9 / 15.3 / 16.4 | 15.1 / 18.4 / 34.0 | 20.4 / 21.5 / 22.9 |
| `find_reading_sentences` | 2.8 / 3.7 / 4.1 | 32.3 / 42.8 / 92.8 | 71.4 / 84.3 / 120.0 |

**The four variants, worst single call** (all four were run twice; the
second, quiet run is shown, because the first overlapped spike 3's Grafana
run):

| Recommender | jit on | jit off |
|---|---|---|
| v1, as first written | 613 ms ✗ | 292 ms ✗ |
| **v2, unknown kanji by a join** | **120 ms ✓** | 191 ms ✓ |

- **What went wrong in v1:** its per-word `ARRAY(...)` of unknown kanji is
  planned three times (filter, join key, output). That inflates the cost
  estimate to 1.6 million, which crosses Postgres's JIT threshold, and JIT
  then takes about 300 ms to compile a query that runs in 38 ms. v2
  computes the unknown kanji once with a join and a `GROUP BY`, and its
  cost stays under the threshold.
- **The slowest call in every run is the reading query** at 500 known
  words (p50 about 72 ms). In the first, noisy run of v2 with jit off, one
  call took 1,608 ms while Grafana was being measured alongside. In the
  quiet run it stayed at 191 ms or less.

**Beyond the pass rule** (direct SQL, jit off, [results-growth.md](results-growth.md)):

| Known words | `recommend_words` N3, p95 | Reading query, p50 / p95 |
|---|---|---|
| 500 | 15 ms | 74 / 91 ms |
| 1,000 | 16 ms | 124 / 145 ms |
| 2,000 | 19 ms | 164 / **208 ms** |
| 4,000 | 17 ms | 189 / **219 ms** |

The recommender stays flat. **The reading query grows with the known set**
(it counts known words across every sentence that contains one) and
crosses 200 ms at about 2,000 known words, which is about where an N3
learner is.

## What it changes in the plan

- **Proposed for slice 2:** the known-words read and the dictionary query
  are two round trips by design, because Juku's MCP server reads two
  databases (ADR-006's diagram). Say so in ADR-006, or put the precomputed
  recommender tables in the app database. Either works; the timings above
  include both reads.
- **Proposed for slice 2:** set `jit = off` on the Juku MCP server's
  database role. Its queries are short and run many times, so JIT only
  costs. Add an FF (or a test) that runs EXPLAIN on each tool query and
  fails if JIT kicks in or the plan's cost explodes. That's the kind of
  regression FF1 is meant to catch.
- **Proposed for LE4 (Should), before it's built:** don't scan all
  sentences per request. Either keep a per-learner "unknown count" per
  sentence, updated as words become known (the scale path's incremental
  summaries), or look sentences up by the one target word and check the
  rest. Both stay flat as the known set grows.
- **To settle in slice 2:** ADR-010 doesn't say where words with no new
  kanji (kana words, or all kanji known) rank against the leverage key.
  Here they count as leverage 0, so they come after new-kanji words within
  the same tier. The function words (particles, copula, auxiliaries,
  conjunctions) are taken as known in reading practice; that also needs a
  line in LE4.
