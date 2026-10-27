# Slice Plan and Cost Model

## Prerequisites (outside this repo)

Building starts only when **all** of these hold. Nothing here is planned
to start sooner.

| # | Prerequisite | Who |
|---|---|---|
| P1 | The open server-security follow-ups are cleared: key rotations, and key-only SSH on the second server | Arthur |
| P2 | The gateway is pushed | Arthur |
| P3 | The model budget is topped up ($5), and a new key is created with its cap (about $4.50) | Arthur, when building starts |
| P4 | A subdomain for the app and one for the dashboard | Arthur |
| P5 | Arthur has joined a JLPT study group as a member (any time; joining isn't building) | Arthur |

## Spikes (local, $0)

| # | Question | Method | Pass | Time |
|---|---|---|---|---|
| 1 | How big is the dictionary in Postgres, and how long does it take to load? | Load JMdict, KANJIDIC2 and Tatoeba into a local `postgres:16`; record row counts, disk size and load time | Under 1 GB on disk; a repeatable load | 2 h |
| 2 | Do the recommender and i+1 queries fit the limits? | Run them in Juku's MCP server prototype with 0, 100 and 500 known words; time them | Under 200 ms each, at every size | 1 h |
| 3 | Does Grafana fit? | Grafana OSS with a provisioned Postgres data source and one dashboard; read its idle memory | Idle well under 256 MB. Otherwise, fall back to cron alerts (ADR-009) | 1 h |
| 4 | How cleanly do the JLPT lists and Tatoeba's index map to JMdict? | Match by spelling and reading; count ambiguous and unmatched entries, and the share of sentences that are fully indexed | Counted and reported; rules for the ambiguous ones written down | 1.5 h |
| 5 | Does Sumopod report cached input tokens? | Read the usage fields in existing harness logs (no new calls) | Answered either way; the cost model is updated | 15 min |
| 6 | Does the delegation chain hold through the gateway? | First, read the MCP authorization spec current at build time (Arthur notes a July 2026 revision). Prototype Juku's MCP server with a signed token in `_meta`, through a local gateway. Try: another learner's rows; a widened scope; an expired, replayed or wrong-audience token; a chain 3 hops deep; Keiko's key carrying Shiori's chain | The gateway passes `_meta` through unchanged; every attempt fails and is logged | 3 h |

## Slices

**Evaluation-driven order (ADR-015):** in every slice, the tests, eval
tasks and fixtures are committed first and fail against a stub. Then the
code is written until they pass. Each guardrail's test comes before the
guardrail. Git history is the evidence (Phase 1, EDD1).

**Standard checks:** every step follows
[standard-checks.md](standard-checks.md):
- `make check` on every commit;
- the end-of-slice list;
- the specific checks wherever something can go wrong;
- the lists before paid runs, server steps and publishing.

A failed check stops the step.

**Fitness functions (ADR-023)** join CI as their slice lands:
- FF1–FF3 and FF6 with the learning engine and the pipeline;
- FF4 and FF5 from slice 1;
- FF7 with the pipeline;
- FF8 and FF9 with slice 3.

From then on, a red fitness function blocks the merge.

| Slice | Delivers | Done when | Model cost |
|---|---|---|---|
| **1. Data** | Load scripts with pinned versions and checksums; the dictionary update policy (pinned version, mapping removed entries); the "about the data" page with licences; views and schema comments; row counts committed; CI with FF4 and FF5 | One command rebuilds the dictionary database; licences checked | $0 |
| **2. Learning engine** | The data design from the scale path (event table partitioned by month, incremental summaries, `cohort_id`, timezones); input normalization; known words, coverage, quizzes (generation and grading) and Susumu, the recommender, with fixture learners and tests (mutation-checked); a synthetic 5,000-learner database for FF1 | Exact outputs match the fixtures; FF1–FF3 green | $0 |
| **3. Juku's MCP server, identity and guardrails** | The scoped tools, including `get_memory` and `request_replan`; per-agent identities; delegation tokens and their checks; `guardrails.yaml` and its tests; spans | The cross-learner suite (M7) and the delegation suite (ID2) pass, and are mutation-checked: removing any check makes a test fail. Every guardrail has its test (G1) | $0 |
| **4. Memory** | The notes table, evidence checks, allowed categories, consolidation, and the "Shiori ingat…" page | Fixtures: a note without evidence, with someone else's evidence, or in a forbidden category is refused; a stale note lapses | $0 |
| **5. Thin app** | Pages, consent, 18+, invite codes, Hapus data saya, ratings, the budget guard; chat with a scripted model (record and replay) and the citation check | Deletion cascades everywhere; per-call records and traces hold no content; the guard stops at each cap; a fabricated citation is flagged | $0 |
| **6. Pipeline and monitoring** | Keiko, Nikki and Tadashi with scripted models; code approval; the facts-only fallback; cron; the run records and Run Inspector; Grafana and alerts | A planted bad number, an off-level word and a stale claim are each blocked in code; each alert fired on purpose and received | $0 |
| **7. Evals, safety and baseline** | The task sets already committed (40 chat, 15 memory, 10 pipeline fixtures); the attack suite with its committed prediction; rubrics for the hand checks; baseline runs, and a run choosing the reasoning effort | The attack suite runs with the scripted agent, with and without the gateway ($0). Q1 ≥ 90% and MEM1 ≥ 90%: the launch gate. Then one real-model safety run. **First paid runs, with Arthur's OK** | ~$1.17 |
| **8. Deploy and dogfood** | Compose on the server (through Arthur); the gateway in front of both MCP servers; Arthur uses it for 4–5 days, with the weekly pipeline triggered on demand twice | Alert delivery tested on the server; one end-to-end trace seen; dogfood issues fixed | ~$0.40 |
| **9. Launch and window** | Arthur posts the invitation and hands out codes; 4 counted weeks; the weekly review: failures become tasks, then fixes, then reruns | The window closes on its date, whatever the numbers | the pools below, plus ~$0.60 of reruns |
| **10. Evidence and write-up** | Evidence SQL and outputs; the privacy check; the case study, JOURNEY and a portfolio entry (EN, JA, ID); text deletion scheduled for 60 days later | Every number traces to a file; the privacy check passes | $0 |
| **Should** | The load test (Locust, 5,000 synthetic learners, scripted model) and its FF10 baseline | Numbers published, labelled as a measurement of the design | $0 |
| **Should** | Reading practice, the pace planner, the mistakes queue, the feedback job | Built before launch if they fit; otherwise during the window behind a flag, with the switch-on date recorded so metrics aren't mixed silently | $0, except the feedback job (~$0.01 a week, from the reserve) |

**Rushed order (Phase 2, Time budget):**
- slices 1–2 are track A;
- slice 3 is track B;
- slice 5, with the frontend (FE1–FE7) and FF12, is track C;
- the monitoring half of slice 6, with the CI fitness functions, is
  track D.

The four run in parallel in weeks 1–2, each in its own session and
files. Slice 4 and the pipeline half of slice 6 (track E) follow in week
2–3. Slice 8's dogfooding triggers the weekly pipeline on demand, rather
than waiting for two Sundays.

Slices 1–6 are local and free, so they can be built before the budget
exists. The paid work starts at slice 7.

## Cost model

**Prices:** gpt-5-mini through Sumopod costs $0.25 per million input
tokens and $2.00 per million output tokens. Source: the harness's
`prices.yaml`, from Sumopod's pricing table, checked 2026-10-23. Recheck
before slice 7.

**The measured basis:** agent-eval-harness ran 200 agent tasks over Pagila
with this model for $0.534, about **$0.0027 a question**, including schema
exploration and tool calls.

**Most of Juku costs nothing.** Quizzes, recommendations, reading, the
plan and the memory page make no model call. The model is used for chat
and the weekly report only.

**One chat question** (an estimate, checked in slice 7):

| Part | Tokens |
|---|---|
| System prompt, with a compact schema summary | ~2,000 |
| Three model calls (look up, query, answer), with input re-sent and growing each call | ~12,000 input in total |
| Tool calls, reasoning, and an Indonesian answer of about 400 tokens | ~1,100 output in total |
| **Cost** | 12,000 × $0.25/M + 1,100 × $2.00/M ≈ **$0.0052** |

The planning figure is **$0.005 a question**, about twice the measured
basis.

**One weekly report** (an estimate):

| Step | Input | Output | Cost |
|---|---|---|---|
| Keiko: three calls, reading the facts and memory through Juku's MCP server | ~13,500 | ~1,000 | $0.0054 |
| Tadashi reviews the plan | ~4,000 | ~400 | $0.0018 |
| Nikki writes the report | ~5,000 | ~1,200 | $0.0037 |
| Tadashi reviews the report | ~4,000 | ~400 | $0.0018 |
| Revisions (about 30% of outputs, one each) | | | ~$0.0012 |
| **Total** | | | **~$0.014** |

The planning figure is **$0.015 a report**.

**A session** mixes free activity with about 2 chat questions: **~$0.01**.

**The budget:**

| Line | Calculation | Cost |
|---|---|---|
| Baseline chat eval | 40 tasks × 2 epochs × $0.005 | $0.40 |
| Reasoning-effort choice | 40 tasks × 1 × $0.005 | $0.20 |
| Pipeline fixtures | 10 learners × 2 runs × $0.015 | $0.30 |
| Memory tasks | 15 × 2 × $0.005 | $0.15 |
| Safety eval, real model, once | ~15 attack tasks × ~1.6 calls × $0.005 | $0.12 |
| Smoke tests and dogfood | ~50 questions and 2 reports, with retries | $0.40 |
| Weekly reruns during the window | 3 × 40 tasks × $0.005 | $0.60 |
| Reserve (price change, retries, a low estimate, the feedback job) | | $0.23 |
| **Fixed total** | | **$2.40** |
| **Reports pool** (reserved) | 60 reports × $0.015 | **$0.90** |
| **Chat pool** (the B1 hard stop) | $4.50 − $2.40 − $0.90 | **$1.20** ≈ 240 questions |
| **Key cap** | | **$4.50** |
| Left on the account, never reachable by the key | $5.00 − $4.50 | $0.50 |

**Expected use:**

| Case | Learners | Reports | Chat questions | User spend | Total |
|---|---|---|---|---|---|
| Floor | 5 | 15 | 60 | $0.53 | $2.93 |
| Target | 10, ~80 sessions | 40 | 160 | $1.40 | $3.80 |
| High | 15, ~180 sessions | 60 | 360, **capped at 240** | $2.10 | $4.50 |

- **In the high case, chat stops before the window ends,** and that is
  reported as a finding. Reports and every $0 feature carry on.
- **Daily chat caps** (B1): 20 questions per learner (at most $0.10 a
  person a day), and $0.20 a day in total. The pool's hard stop binds over
  the window; the daily caps stop one bad day, such as a leaked code, from
  draining it.
- **The speaking partner (Could)** draws on the chat pool at about $0.015
  a conversation. It is switched on only if chat spend is under plan at
  week 2.

**Levers if spend runs high**, each measured, not assumed:
1. Put the compact schema in the system prompt, so fewer calls go to
   `describe_table` (also an M3 change).
2. Prompt caching on repeated prompts, if spike 5 shows Sumopod serves
   cached input at a tenth of the price.
3. Route "what should I learn" questions to the $0 recommender.
4. gpt-5-nano as a fallback near a pool's end (Could; 91% vs 96% on
   Pagila).

Cost per question, per report, per session and in total is published from
the records, next to these estimates, including where they were wrong.
