Start: load averages: 16.88 17.90 10.88. End: load averages: 13.54 17.04 10.78.

OpenJLPT tables, jit on; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 6.2 / 9.7 / 11.6 | 5.7 / 9.1 / 10.6 | 10 |
| N5 | 0 | `find_reading_sentences` | 2.7 / 4.6 / 10.9 | 2.4 / 4.2 / 9.9 | 10 |
| N5 | 100 | `recommend_words` | 6.2 / 9.4 / 16.0 | 5.7 / 9.0 / 15.2 | 10 |
| N5 | 100 | `find_reading_sentences` | 6.7 / 12.8 / 16.0 | 6.0 / 11.8 / 14.4 | 10 |
| N5 | 500 | `recommend_words` | 10.8 / 20.0 / 56.0 | 10.1 / 18.8 / 55.3 | 10 |
| N5 | 500 | `find_reading_sentences` | 12.1 / 27.7 / 127.6 | 11.6 / 26.2 / 126.4 | 10 |
| N4 | 0 | `recommend_words` | 8.8 / 12.3 / 16.0 | 8.4 / 10.9 / 15.4 | 10 |
| N4 | 100 | `recommend_words` | 8.9 / 20.2 / 73.9 | 8.4 / 19.3 / 73.0 | 10 |
| N4 | 500 | `recommend_words` | 9.9 / 19.5 / 41.5 | 9.5 / 19.0 / 40.6 | 10 |
| N3 | 0 | `recommend_words` | 20.3 / 37.6 / 87.5 | 19.7 / 36.5 / 86.5 | 10 |
| N3 | 100 | `recommend_words` | 17.2 / 35.1 / 72.5 | 16.7 / 33.8 / 70.9 | 10 |
| N3 | 500 | `recommend_words` | 17.9 / 27.9 / 110.0 | 17.4 / 26.9 / 109.4 | 10 |
| N2 | 0 | `recommend_words` | 42.8 / 99.1 / 148.4 | 41.8 / 94.0 / 147.3 | 10 |
| N2 | 100 | `recommend_words` | 40.8 / 83.8 / 142.3 | 39.9 / 77.3 / 141.2 | 10 |
| N2 | 500 | `recommend_words` | 69.8 / 130.2 / 147.8 | 69.1 / 127.4 / 145.0 | 10 |

Worst single round trip: **148.4 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [results-jit-off-quieter.md](results-jit-off-quieter.md); this run's full file is on the spike branch: [openjlpt/results-jit-on.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/openjlpt/results-jit-on.md).
