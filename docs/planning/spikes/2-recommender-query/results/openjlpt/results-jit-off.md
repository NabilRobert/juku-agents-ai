Start: load averages: 13.54 17.04 10.78. End: load averages: 14.56 17.07 11.05.

OpenJLPT tables, jit off; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 14.1 / 28.7 / 36.6 | 13.0 / 26.6 / 33.8 | 10 |
| N5 | 0 | `find_reading_sentences` | 15.3 / 41.1 / 166.3 | 13.5 / 39.6 / 147.7 | 10 |
| N5 | 100 | `recommend_words` | 13.7 / 22.7 / 55.3 | 12.8 / 21.0 / 46.1 | 10 |
| N5 | 100 | `find_reading_sentences` | 11.4 / 24.3 / 63.6 | 10.5 / 23.2 / 46.4 | 10 |
| N5 | 500 | `recommend_words` | 12.8 / 18.1 / 22.3 | 12.1 / 16.8 / 20.7 | 10 |
| N5 | 500 | `find_reading_sentences` | 17.1 / 36.1 / 67.4 | 16.4 / 34.6 / 66.8 | 10 |
| N4 | 0 | `recommend_words` | 22.1 / 37.7 / 76.7 | 20.6 / 36.1 / 69.6 | 10 |
| N4 | 100 | `recommend_words` | 20.2 / 44.7 / 112.1 | 18.9 / 42.8 / 108.9 | 10 |
| N4 | 500 | `recommend_words` | 24.4 / 47.1 / 97.4 | 23.2 / 45.0 / 96.2 | 10 |
| N3 | 0 | `recommend_words` | 25.1 / 53.6 / 112.5 | 24.3 / 51.5 / 110.0 | 10 |
| N3 | 100 | `recommend_words` | 21.4 / 29.6 / 35.0 | 20.8 / 28.8 / 34.1 | 10 |
| N3 | 500 | `recommend_words` | 22.3 / 31.5 / 87.8 | 21.6 / 30.5 / 86.6 | 10 |
| N2 | 0 | `recommend_words` | 29.1 / 50.8 / 118.7 | 28.5 / 49.8 / 117.7 | 10 |
| N2 | 100 | `recommend_words` | 35.3 / 70.5 / 111.7 | 34.3 / 69.4 / 109.9 | 10 |
| N2 | 500 | `recommend_words` | 63.7 / 110.7 / 242.0 | 63.1 / 110.1 / 240.2 | 10 |

Worst single round trip: **242.0 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [results-jit-off-quieter.md](results-jit-off-quieter.md); this run's full file is on the spike branch: [openjlpt/results-jit-off.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/openjlpt/results-jit-off.md).
