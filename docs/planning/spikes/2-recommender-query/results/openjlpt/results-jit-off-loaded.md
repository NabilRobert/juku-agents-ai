Run under load: load averages: 16.88 17.90 10.88

OpenJLPT tables, jit off; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 6.5 / 10.4 / 19.1 | 6.1 / 9.5 / 18.2 | 10 |
| N5 | 0 | `find_reading_sentences` | 2.0 / 2.9 / 4.4 | 1.7 / 2.6 / 4.1 | 10 |
| N5 | 100 | `recommend_words` | 6.3 / 12.7 / 40.7 | 5.9 / 11.8 / 39.5 | 10 |
| N5 | 100 | `find_reading_sentences` | 6.0 / 15.5 / 19.7 | 5.6 / 14.4 / 17.9 | 10 |
| N5 | 500 | `recommend_words` | 9.1 / 27.8 / 53.9 | 8.7 / 25.7 / 37.0 | 10 |
| N5 | 500 | `find_reading_sentences` | 11.8 / 22.6 / 27.3 | 11.2 / 22.0 / 26.7 | 10 |
| N4 | 0 | `recommend_words` | 7.7 / 11.2 / 15.9 | 7.2 / 10.3 / 15.0 | 10 |
| N4 | 100 | `recommend_words` | 8.9 / 16.0 / 80.1 | 8.5 / 15.0 / 77.7 | 10 |
| N4 | 500 | `recommend_words` | 10.7 / 18.0 / 31.0 | 10.3 / 17.2 / 29.8 | 10 |
| N3 | 0 | `recommend_words` | 21.6 / 33.4 / 80.5 | 20.7 / 32.1 / 79.1 | 10 |
| N3 | 100 | `recommend_words` | 14.6 / 27.6 / 50.0 | 14.1 / 26.5 / 48.3 | 10 |
| N3 | 500 | `recommend_words` | 16.7 / 33.3 / 57.7 | 16.2 / 32.3 / 56.3 | 10 |
| N2 | 0 | `recommend_words` | 18.5 / 24.7 / 30.8 | 18.1 / 24.1 / 30.2 | 10 |
| N2 | 100 | `recommend_words` | 19.4 / 33.2 / 57.4 | 19.0 / 32.5 / 56.7 | 10 |
| N2 | 500 | `recommend_words` | 82.2 / 192.8 / 274.0 | 80.8 / 192.1 / 271.6 | 10 |

Worst single round trip: **274.0 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [results-jit-off-quieter.md](results-jit-off-quieter.md); this run's full file is on the spike branch: [openjlpt/results-jit-off-loaded.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/openjlpt/results-jit-off-loaded.md).
