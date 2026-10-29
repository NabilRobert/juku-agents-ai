Query v2, jit off.

<!-- learner_word rows: 2,125,332 -->
| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 4.2 / 4.6 / 5.3 | 4.0 / 4.4 / 5.0 | 10 |
| N5 | 0 | `find_reading_sentences` | 3.1 / 3.4 / 3.6 | 2.7 / 2.9 / 3.1 | 10 |
| N5 | 100 | `recommend_words` | 5.0 / 5.8 / 6.8 | 4.5 / 5.3 / 5.5 | 10 |
| N5 | 100 | `find_reading_sentences` | 32.2 / 41.4 / 63.2 | 31.6 / 40.9 / 62.1 | 10 |
| N5 | 500 | `recommend_words` | 5.2 / 8.6 / 11.5 | 4.9 / 8.2 / 10.9 | 10 |
| N5 | 500 | `find_reading_sentences` | 72.4 / 117.5 / 191.3 | 71.6 / 116.5 / 190.4 | 10 |
| N4 | 0 | `recommend_words` | 7.4 / 7.9 / 52.5 | 6.3 / 6.7 / 41.9 | 10 |
| N4 | 100 | `recommend_words` | 7.5 / 7.9 / 8.9 | 6.5 / 6.7 / 7.7 | 10 |
| N4 | 500 | `recommend_words` | 8.3 / 8.7 / 9.6 | 7.2 / 7.5 / 8.5 | 10 |
| N3 | 0 | `recommend_words` | 11.2 / 12.4 / 29.9 | 10.1 / 11.1 / 29.1 | 10 |
| N3 | 100 | `recommend_words` | 10.9 / 12.1 / 33.8 | 10.0 / 10.7 / 33.1 | 10 |
| N3 | 500 | `recommend_words` | 12.1 / 12.6 / 13.1 | 11.0 / 11.5 / 12.1 | 10 |
| N2 | 0 | `recommend_words` | 14.7 / 21.9 / 32.5 | 13.6 / 21.4 / 32.0 | 10 |
| N2 | 100 | `recommend_words` | 14.3 / 16.3 / 46.2 | 14.0 / 16.0 / 45.5 | 10 |
| N2 | 500 | `recommend_words` | 19.2 / 26.1 / 34.2 | 18.9 / 25.5 / 33.6 | 10 |

Worst single round trip: **191.3 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [openjlpt/results-jit-off-quieter.md](openjlpt/results-jit-off-quieter.md); this run's full file is on the spike branch: [results-v2-jit-off.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/results-v2-jit-off.md).
