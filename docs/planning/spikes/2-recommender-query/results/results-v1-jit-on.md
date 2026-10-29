Query v1, jit on.

<!-- learner_word rows: 2,125,332 -->
| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 23.5 / 36.1 / 222.0 | 22.7 / 35.5 / 221.4 | 10 |
| N5 | 0 | `find_reading_sentences` | 3.3 / 4.5 / 7.9 | 2.9 / 4.2 / 7.5 | 10 |
| N5 | 100 | `recommend_words` | 232.3 / 411.8 / 549.5 | 230.6 / 411.0 / 548.5 | 10 |
| N5 | 100 | `find_reading_sentences` | 40.7 / 141.4 / 208.1 | 40.2 / 140.3 / 207.4 | 10 |
| N5 | 500 | `recommend_words` | 261.7 / 461.3 / 541.2 | 261.1 / 457.1 / 540.1 | 10 |
| N5 | 500 | `find_reading_sentences` | 80.1 / 134.5 / 146.5 | 79.7 / 134.0 / 146.1 | 10 |
| N4 | 0 | `recommend_words` | 215.9 / 276.8 / 557.7 | 215.1 / 275.7 / 557.3 | 10 |
| N4 | 100 | `recommend_words` | 247.2 / 326.2 / 456.1 | 246.7 / 325.4 / 455.3 | 10 |
| N4 | 500 | `recommend_words` | 223.6 / 402.1 / 613.2 | 223.0 / 391.4 / 608.6 | 10 |
| N3 | 0 | `recommend_words` | 228.5 / 259.9 / 341.4 | 227.9 / 259.4 / 340.6 | 10 |
| N3 | 100 | `recommend_words` | 216.2 / 289.4 / 453.6 | 215.1 / 288.6 / 453.0 | 10 |
| N3 | 500 | `recommend_words` | 230.4 / 341.0 / 477.2 | 229.7 / 340.2 / 476.5 | 10 |
| N2 | 0 | `recommend_words` | 231.0 / 312.3 / 378.8 | 230.1 / 311.5 / 378.0 | 10 |
| N2 | 100 | `recommend_words` | 262.4 / 349.8 / 485.5 | 261.4 / 348.8 / 484.2 | 10 |
| N2 | 500 | `recommend_words` | 251.5 / 383.6 / 426.4 | 250.9 / 383.1 / 424.9 | 10 |

Worst single round trip: **613.2 ms** (limit 200 ms).

The sample outputs (the first four results of each run) are left out on main to keep it small: they're near-identical across these runs, and no doc cites them. One set is kept in [openjlpt/results-jit-off-quieter.md](openjlpt/results-jit-off-quieter.md); this run's full file is on the spike branch: [results-v1-jit-on.md](https://github.com/NabilRobert/juku-agents-ai/blob/spike/recommender-query/spikes/2-recommender-query/results-v1-jit-on.md).
