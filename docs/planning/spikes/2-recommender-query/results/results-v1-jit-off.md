Query v1, jit off.

<!-- learner_word rows: 2,125,332 -->
| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 5.2 / 7.1 / 76.4 | 4.9 / 6.7 / 75.7 | 10 |
| N5 | 0 | `find_reading_sentences` | 3.8 / 6.2 / 14.0 | 3.1 / 5.4 / 13.5 | 10 |
| N5 | 100 | `recommend_words` | 6.2 / 7.3 / 9.0 | 5.7 / 6.8 / 8.1 | 10 |
| N5 | 100 | `find_reading_sentences` | 33.5 / 43.5 / 98.4 | 32.4 / 42.9 / 97.4 | 10 |
| N5 | 500 | `recommend_words` | 5.0 / 6.1 / 7.7 | 4.8 / 5.8 / 7.4 | 10 |
| N5 | 500 | `find_reading_sentences` | 77.3 / 136.9 / 185.1 | 76.9 / 136.4 / 184.4 | 10 |
| N4 | 0 | `recommend_words` | 9.1 / 15.1 / 27.7 | 8.6 / 14.7 / 27.3 | 10 |
| N4 | 100 | `recommend_words` | 7.8 / 10.8 / 12.6 | 7.6 / 10.2 / 12.2 | 10 |
| N4 | 500 | `recommend_words` | 8.8 / 10.9 / 12.7 | 8.5 / 10.5 / 12.5 | 10 |
| N3 | 0 | `recommend_words` | 15.1 / 27.6 / 43.0 | 14.3 / 24.4 / 40.4 | 10 |
| N3 | 100 | `recommend_words` | 16.0 / 19.0 / 24.6 | 15.1 / 18.3 / 22.4 | 10 |
| N3 | 500 | `recommend_words` | 18.0 / 27.6 / 291.7 | 17.4 / 26.3 / 291.0 | 10 |
| N2 | 0 | `recommend_words` | 20.7 / 22.7 / 36.6 | 19.9 / 21.5 / 35.9 | 10 |
| N2 | 100 | `recommend_words` | 22.2 / 35.4 / 69.0 | 21.1 / 33.5 / 66.6 | 10 |
| N2 | 500 | `recommend_words` | 26.4 / 31.7 / 75.9 | 25.9 / 31.2 / 75.5 | 10 |

Worst single round trip: **291.7 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [openjlpt/results-jit-off-quieter.md](openjlpt/results-jit-off-quieter.md); this run's full file is on the spike branch: [results-v1-jit-off.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/results-v1-jit-off.md).
