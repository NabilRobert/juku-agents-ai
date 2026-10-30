# Load test results (FF10)

A measurement of the design on one laptop, not a claim that 5,000 people have
used Juku. Measured on 2026-10-30 with `evals/load/run.py`, $0 spent.

**Set-up:** 5,000 synthetic learners and 2.57 million learning events. The app,
juku-mcp and Postgres run in containers at their production caps. The model is
scripted, so chat times are Juku's own work plus one real MCP call, with no
model time. Locust ran on the same laptop, and other work was running on it.

## Results

Each step ran for 90 seconds, with 2-8 seconds between a learner's actions.
The $0 path is every page and write that needs no model.

| Learners on at once | $0 requests/s | $0 p50 | $0 p95 | $0 p99 | Chat p95 | Failed requests | Restarts |
|---|---|---|---|---|---|---|---|
| 50 | 22.9 | 8 ms | 53 ms | 96 ms | 86 ms | 0 | 0 |
| 100 | 47.5 | 9 ms | 66 ms | 162 ms | 227 ms | 0 | 0 |
| 200 | 95.8 | 17 ms | 140 ms | 302 ms | 407 ms | 0 | 0 |
| 400 | 146.8 | 500 ms | 1,595 ms | 2,257 ms | 2,621 ms | 0 | 0 |

**Reading it:** 200 learners on at once is comfortable, well inside the 1 s
budget for $0 pages. At 400 the app is out of CPU (one Uvicorn process at about
100%), throughput stops rising with users, and p95 misses that budget. The
limit between 200 and 400 wasn't measured. The app is the bottleneck, not
Postgres (64% at most) or juku-mcp (9%).

| Other measurements | Result |
|---|---|
| Peak memory against caps | app 190 of 256 MiB, juku-mcp 83 of 128 MiB, Postgres 575 MiB of 1 GiB |
| Chat answers | 839 of 839 stored as verified |
| Weekly pipeline, no model time | 300 learners in 25.6 s, all published: 85 ms each, about 7 minutes for 5,000 |
| Delegation chain, p50 | minting under 0.1 ms, verifying 0.2 ms per call |
| Database size | 1.46 GB for 5,000 learners; about 360 bytes per new event |

**The weekly run with a model:** `run_due` takes learners one at a time. At an
assumed 3 model calls of 10 s each, 5,000 learners would take about 42 hours.
That doesn't fit a Sunday evening, so the batch path in
`docs/planning/scale-path.md` matters at that size. The model time here is an
assumption, not a measurement.

## Why FF10 isn't a gate yet

Ten runs of the 200-learner step on unchanged code gave a $0 p95 of 98, 116,
132, 140, 140, 171, 183, 216, 226 and 288 ms, while p50 stayed near 20 ms.
Restarting the app made no consistent difference, memory stayed flat, and all
routes moved together, so this looks like a busy laptop rather than a leak.

FF10 allows 20%, so it would fail on unchanged code here. It stays `pending`
until a baseline comes from a quiet machine. `guardrails.yaml` holds the median
of these runs (155 ms), and `run.py check` judges the median of three runs.

## What the test found

| Finding | Severity | Status |
|---|---|---|
| Neither image could start: scripts pointed at a venv path that didn't exist | Crash | Fixed |
| juku-mcp refused every gateway call with 421: Host `juku-mcp:8000` wasn't allowed | Crash | Fixed |
| A report citing an all-digit word ID (72 of 7,811 words) was blocked as an invented number, so 9 of 300 learners got the facts-only report | Wrong result | Fixed |
| Chat has no error path: a model or tool failure ends the stream with no `done` event and no message for the learner | Silent failure | Open |
| Uvicorn closes idle connections after 5 s, so a client reusing one at that moment is dropped. Reproduced directly. A proxy reusing connections could hit the same race (suspected, not tested) | Dropped requests | Open; the load test keeps connections open for 30 s |
| One `connection is closed` traceback per run, as Locust stopped mid-request. No request failed (suspected harmless) | Logs only | Open |

Three of these came from the test's own stack, not from Juku: the scripted
model crashed on a learner with no words left to recommend, Locust counted a
dropped connection as an unverified answer, and a failed Locust step ended the
run and left the process hanging. All three are fixed here.
