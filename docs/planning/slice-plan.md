# Slice Plan and Cost Model

## Prerequisites (outside this repo)

Building starts only when **all** of these hold. Nothing here is planned
to start sooner.

| # | Prerequisite | Who |
|---|---|---|
| P1 | The open server-security follow-ups are cleared: key rotations, and key-only SSH on the second server | Arthur |
| P2 | The gateway is pushed | Arthur |
| P3 | The model budget is topped up ($5), and the new key is created with its cap (about $4.50) | Arthur, when building starts |
| P4 | A subdomain for the app and one for the dashboard | Arthur |
| P5 | Arthur has joined a JLPT study group as a member (any time; joining isn't building) | Arthur |

## Spikes (local, $0)

| # | Question | Method | Pass | Time |
|---|---|---|---|---|
| 1 | How big is the dictionary in Postgres, and how long does it take to load? | Load JMdict and KANJIDIC2 into a local `postgres:16`; record row counts, disk size and load time | Under 1 GB on disk; the load script is repeatable | 2 h |
| 2 | Does the recommender query pass MCP-backbone's validator and cost check? | Run the R2 query through a local MCP-backbone with 0, 100 and 500 known IDs | Accepted at every size; well under the cost limit | 1 h |
| 3 | Does Grafana fit? | Grafana OSS with a provisioned Postgres data source and one dashboard; read its idle memory | Idle well under 256 MB. Otherwise, fall back to cron alerts (ADR-008) | 1 h |
| 4 | How cleanly do JLPT lists map to JMdict entries? | Match a community list by spelling and reading; count ambiguous and unmatched entries | Counted and reported; rules for the ambiguous ones written down | 1 h |
| 5 | Does Sumopod report cached input tokens? | Read the usage fields in existing harness logs (no new calls) | Answered either way; the cost model is updated | 15 min |

## Slices

| Slice | Delivers | Done when | Model cost |
|---|---|---|---|
| **1. Data** | Load scripts with pinned versions and checksums; the "about the data" page with licences; views and schema comments (D4); row counts committed | One command rebuilds the dictionary database from the downloads; licences checked | $0 |
| **2. Recommender** | The precomputed tables, the R2 query, fixture learners and tests (mutation-checked) | Exact top-10 output matches the fixtures; spike 2's limits hold | $0 |
| **3. Thin app** | Chat with a scripted model (record and replay, no paid calls); consent, 18+, invite codes, nicknames; the citation check; ratings; Hapus data saya; the budget guard | Tests pass: deletion cascades; per-call records and traces hold no content; the guard stops at each cap; the citation check flags a fabricated ID | $0 |
| **4. Monitoring** | Per-call records; Grafana dashboards and alert rules from committed files; the heartbeat; the gateway audit import with chain verification | Each alert fired on purpose and received; a dashboard row leads to its trace; no panel can show a user | $0 |
| **5. Eval and baseline** | The ~40-task set in agent-eval-harness, with gold answers from SQL; the rubric for Q3; a baseline run, and a run choosing the reasoning effort | Q1 ≥ 90% (the launch gate). **First paid run, with Arthur's OK** | ~$0.60 |
| **6. Deploy and dogfood** | Compose on the server (through Arthur); the gateway in front of MCP-backbone for this app; Arthur uses it for a week | Alert delivery tested on the server (Phase 1, M6); one end-to-end trace seen; dogfood issues fixed | ~$0.40 |
| **7. Launch and window** | Arthur posts the invitation and hands out codes; 4 counted weeks; a weekly review turns failures into tasks, fixes and reruns | The window closes on its date, whatever the numbers | user pool ≤ $2.50, plus ~$0.60 of reruns |
| **8. Evidence and write-up** | Evidence SQL and outputs; the privacy check; the case study, JOURNEY and a portfolio entry (EN, JA, ID); text deletion scheduled for 60 days later | Every number traces to a file; the privacy check passes | $0 |

Slices 1–4 are local and free, so they can be done before the budget
exists. The paid work starts at slice 5.

## Cost model

**Prices:** gpt-5-mini through Sumopod costs $0.25 per million input
tokens and $2.00 per million output tokens. Source: the harness's
`prices.yaml`, from Sumopod's pricing table, checked 2026-10-23. Recheck
before slice 5.

**The measured basis:** agent-eval-harness ran 200 agent tasks over
Pagila with this model for $0.534, about **$0.0027 a question**, including
schema exploration and tool calls.

**The estimate for one chat question here** (assumed, then checked in
slice 5):

| Part | Tokens |
|---|---|
| System prompt, with a compact schema summary | ~2,000 |
| Three model calls per question (explore, query, answer); input re-sent and growing each call | ~12,000 input in total |
| Tool calls, reasoning, and an Indonesian answer of about 400 tokens | ~1,100 output in total |
| **Cost** | 12,000 × $0.25/M + 1,100 × $2.00/M ≈ **$0.0052** |

The planning figure is **$0.005 a question**, about twice the measured
basis, to allow for longer Indonesian explanations.

**A session** is about 4 chat questions: ~48k input and ~4.4k output, about
**$0.02**. Recommendations from the button cost $0.

**The budget:**

| Line | Calculation | Cost |
|---|---|---|
| Baseline eval + reasoning-effort choice (slice 5) | 40 tasks × 2 epochs + 40 × 1, × $0.005 | $0.60 |
| Smoke tests and dogfood (slice 6) | ~80 questions × $0.005 | $0.40 |
| Weekly reruns during the window | 3 × 40 tasks × $0.005 | $0.60 |
| Reserve (price change, retries, an estimate that's too low) | | $0.40 |
| **User pool** (the B1 hard stop) | $4.50 − $2.00 | **$2.50** = 500 questions ≈ 125 sessions |
| **Key cap** | | **$4.50** |
| Left on the account, never reachable by the key | $5.00 − $4.50 | $0.50 |

**Expected use against the pool:**

| Case | Sessions | User cost | Total spend |
|---|---|---|---|
| Floor (Phase 1, A3) | 30 | $0.60 | $2.60 |
| Target | 80 (e.g. 10 users, ~2 sessions a week, tapering) | $1.60 | $3.60 |
| High | 180 (15 users × 3 a week × 4 weeks) | capped at $2.50 (125 sessions) | $4.50 |

- **In the high case, the hard stop ends chat early, and that is counted as
  a finding,** not hidden. The Rekomendasi button keeps working at $0.
- **Daily caps** (B1): 20 questions per user a day (at most $0.10 per
  person per day) and $0.20 a day in total (about 10 sessions). The pool's
  hard stop is the binding limit over the window; the daily caps stop a
  single bad day, such as a leaked code, from draining it.

**Levers if spend runs high**, each measured, not assumed:
1. Put the compact schema in the system prompt, so fewer calls go to
   `describe_table`. This is also an M3 change.
2. Prompt caching on the repeated system prompt, if spike 5 shows Sumopod
   serves cached input (cached reads are a tenth of the price).
3. Send "what should I learn" questions to the button path.
4. gpt-5-nano as a fallback near the pool's end (Could; 91% vs 96% on
   Pagila).

The cost per question, per session and in total is published from the
records, next to this estimate, including where the estimate was wrong.
