Quieter run. Start: load averages: 4.39 6.89 8.04. End: load averages: 4.73 6.78 7.97.

OpenJLPT tables, jit on; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 7.2 / 24.9 / 29.3 | 6.7 / 23.9 / 28.0 | 10 |
| N5 | 0 | `find_reading_sentences` | 2.4 / 7.3 / 47.0 | 2.2 / 6.6 / 46.5 | 10 |
| N5 | 100 | `recommend_words` | 6.6 / 14.1 / 19.0 | 6.2 / 13.0 / 18.0 | 10 |
| N5 | 100 | `find_reading_sentences` | 4.7 / 9.0 / 16.1 | 4.4 / 8.6 / 15.4 | 10 |
| N5 | 500 | `recommend_words` | 7.2 / 10.1 / 41.8 | 6.9 / 9.7 / 41.0 | 10 |
| N5 | 500 | `find_reading_sentences` | 10.4 / 16.6 / 36.0 | 10.0 / 16.3 / 35.5 | 10 |
| N4 | 0 | `recommend_words` | 7.4 / 9.1 / 13.2 | 6.8 / 8.2 / 12.1 | 10 |
| N4 | 100 | `recommend_words` | 7.6 / 9.9 / 14.4 | 7.2 / 9.2 / 13.9 | 10 |
| N4 | 500 | `recommend_words` | 9.5 / 11.8 / 26.3 | 8.7 / 10.0 / 25.2 | 10 |
| N3 | 0 | `recommend_words` | 12.6 / 15.5 / 36.4 | 12.1 / 15.1 / 35.6 | 10 |
| N3 | 100 | `recommend_words` | 13.2 / 21.1 / 23.4 | 12.7 / 20.1 / 22.2 | 10 |
| N3 | 500 | `recommend_words` | 15.1 / 29.2 / 59.2 | 14.7 / 28.7 / 58.5 | 10 |
| N2 | 0 | `recommend_words` | 18.9 / 36.7 / 56.3 | 18.3 / 35.8 / 55.3 | 10 |
| N2 | 100 | `recommend_words` | 18.6 / 21.3 / 28.8 | 18.2 / 20.8 / 28.3 | 10 |
| N2 | 500 | `recommend_words` | 48.9 / 76.7 / 123.2 | 48.3 / 75.0 / 122.6 | 10 |

Worst single round trip: **123.2 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [results-jit-off-quieter.md](results-jit-off-quieter.md); this run's full file is on the spike branch: [openjlpt/results-jit-on-quieter.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/openjlpt/results-jit-on-quieter.md).
