Query v2, jit on.

<!-- learner_word rows: 2,125,332 -->
| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 4.2 / 5.0 / 5.6 | 4.0 / 4.8 / 5.3 | 10 |
| N5 | 0 | `find_reading_sentences` | 2.8 / 3.7 / 4.1 | 2.6 / 3.5 / 3.9 | 10 |
| N5 | 100 | `recommend_words` | 4.8 / 6.6 / 7.4 | 4.5 / 6.3 / 7.1 | 10 |
| N5 | 100 | `find_reading_sentences` | 32.3 / 42.8 / 92.8 | 31.0 / 42.3 / 92.1 | 10 |
| N5 | 500 | `recommend_words` | 5.0 / 6.2 / 7.1 | 4.7 / 5.7 / 6.0 | 10 |
| N5 | 500 | `find_reading_sentences` | 71.4 / 84.3 / 120.0 | 70.2 / 83.3 / 119.5 | 10 |
| N4 | 0 | `recommend_words` | 7.4 / 7.8 / 8.9 | 6.4 / 6.6 / 8.0 | 10 |
| N4 | 100 | `recommend_words` | 7.3 / 7.9 / 17.0 | 6.6 / 7.0 / 16.2 | 10 |
| N4 | 500 | `recommend_words` | 7.7 / 13.5 / 69.4 | 7.4 / 13.0 / 67.6 | 10 |
| N3 | 0 | `recommend_words` | 10.6 / 14.6 / 23.9 | 10.3 / 14.1 / 22.8 | 10 |
| N3 | 100 | `recommend_words` | 10.9 / 20.6 / 62.0 | 10.5 / 20.1 / 61.2 | 10 |
| N3 | 500 | `recommend_words` | 11.0 / 13.9 / 49.9 | 10.6 / 13.2 / 48.4 | 10 |
| N2 | 0 | `recommend_words` | 13.9 / 15.3 / 16.4 | 13.3 / 14.3 / 15.1 | 10 |
| N2 | 100 | `recommend_words` | 15.1 / 18.4 / 34.0 | 14.3 / 17.4 / 33.1 | 10 |
| N2 | 500 | `recommend_words` | 20.4 / 21.5 / 22.9 | 19.4 / 20.2 / 21.6 | 10 |

Worst single round trip: **120.0 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [openjlpt/results-jit-off-quieter.md](openjlpt/results-jit-off-quieter.md); this run's full file is on the spike branch: [results-v2-jit-on.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/results-v2-jit-on.md).
