Run under load: load averages: 16.88 17.90 10.88

OpenJLPT tables, jit on; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 5.7 / 8.9 / 13.1 | 5.4 / 8.5 / 12.5 | 10 |
| N5 | 0 | `find_reading_sentences` | 2.4 / 9.3 / 18.1 | 2.1 / 8.3 / 17.5 | 10 |
| N5 | 100 | `recommend_words` | 6.1 / 9.7 / 10.6 | 5.7 / 9.0 / 10.0 | 10 |
| N5 | 100 | `find_reading_sentences` | 4.6 / 6.5 / 76.2 | 4.3 / 6.0 / 75.5 | 10 |
| N5 | 500 | `recommend_words` | 7.4 / 11.1 / 13.6 | 7.0 / 10.5 / 13.1 | 10 |
| N5 | 500 | `find_reading_sentences` | 11.9 / 17.8 / 26.9 | 11.4 / 17.2 / 25.4 | 10 |
| N4 | 0 | `recommend_words` | 9.3 / 14.2 / 31.3 | 8.8 / 13.6 / 30.3 | 10 |
| N4 | 100 | `recommend_words` | 7.7 / 11.6 / 60.0 | 7.3 / 11.0 / 59.5 | 10 |
| N4 | 500 | `recommend_words` | 17.7 / 32.7 / 37.2 | 16.6 / 30.5 / 35.6 | 10 |
| N3 | 0 | `recommend_words` | 13.9 / 22.9 / 71.5 | 13.4 / 22.3 / 70.6 | 10 |
| N3 | 100 | `recommend_words` | 14.1 / 21.4 / 26.4 | 13.6 / 20.5 / 25.7 | 10 |
| N3 | 500 | `recommend_words` | 17.2 / 38.9 / 121.2 | 16.7 / 36.4 / 119.9 | 10 |
| N2 | 0 | `recommend_words` | 20.3 / 27.6 / 41.5 | 19.9 / 26.9 / 40.7 | 10 |
| N2 | 100 | `recommend_words` | 18.9 / 32.9 / 62.9 | 18.5 / 31.8 / 62.3 | 10 |
| N2 | 500 | `recommend_words` | 48.8 / 65.8 / 112.5 | 48.4 / 64.8 / 111.6 | 10 |

Worst single round trip: **121.2 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [results-jit-off-quieter.md](results-jit-off-quieter.md); this run's full file is on the spike branch: [openjlpt/results-jit-on-loaded.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/openjlpt/results-jit-on-loaded.md).
