# Scale Path: Built for Ten, Designed for Thousands

Juku launches for 10–15 learners on a $5 budget, and that's what it is
measured on. This doc records how it would grow to thousands, so the
design doesn't have to be thrown away when it does (Phase 5, ADR-022).

Two rules:
- **Now:** only what is cheap at ten learners and expensive to change
  later. That means the data design, IDs, timezones, and keeping each
  service stateless.
- **Later:** everything else, using existing tools rather than building
  our own. Nothing in the "later" column is claimed as done. The one
  scale claim made is the load test below, and only for what it measures.

## The data design (applies from day one)

**Principles:**
- One narrow, append-only event table is the source of truth for
  learner activity. Everything else is derived from it.
- Derived state is updated incrementally as events arrive, not
  recomputed from all of history, and checked against a full recompute
  nightly.
- Text (chat, reports) is stored apart from numbers, with its own expiry,
  so metrics stay small and deleting text is cheap.
- The dictionary is shared, read-only and the same for everyone. It is
  never copied per learner.

| Table | Shape | Why it scales |
|---|---|---|
| `learning_events` | `bigint` ID, learner ID, cohort ID, event type (`smallint` enum), item ID (dictionary entry or kanji), result, timestamp with time zone. No text | About 40 bytes a row. Partitioned by month, so retention is dropping a partition, not a mass delete. Indexed on (learner, time) |
| `learner_state` | One row per learner and item: box (Leitner), known flag, last seen, counts | Updated as each event arrives. It holds what the recommender, quizzes and reports read, so they never scan history |
| `learner_coverage` | One row per learner and level: words known, kanji known | Incremental counters, so the "how much of N3 do I know" page reads one row |
| `memory_notes` | Category (enum), short text, evidence event IDs, expiry | Small by design, with a cap per learner |
| `chat_messages`, `reports` | Text with an expiry date | Kept apart from the metrics. Deleted by date, in batches |
| `tool_calls`, `pipeline_runs` | Per-call and per-run records, no content | Partitioned by month, like the events |
| `dict.*` | OpenJLPT (words, kanji, grammar, examples), the precomputed recommender tables | Read-only and identical for everyone, so it can be cached or replicated freely |

**From day one, because adding them later is painful:**
- a `cohort_id` on learners and events, for when there's more than one
  study group, class or school. The features stay single-group
  (Phase 1, non-goals); only the column exists;
- the learner's timezone;
- `bigint` keys internally, with a random public ID, so internal IDs never
  appear in URLs;
- `timestamptz` everywhere;
- dictionary entries referenced by their stable IDs, with a recorded
  dictionary version (see "dictionary updates" below).

**Rough size at 5,000 active learners** (an estimate):
- about 200 events a learner a week, at about 60 bytes a row with index
  overhead: about **60 MB a week, about 3 GB a year**;
- summaries: about 5,000 learners × about 2,000 items each, at about
  50 bytes: about 0.5 GB;
- the dictionary: about 1 GB (spike 1 measures it).

One ordinary Postgres server handles that. The pressure at scale is in
model cost and provider limits, not in the data.

## What breaks first, in order

| # | Bottleneck | At 10–15 learners | At thousands | Off-the-shelf answer (recommended) |
|---|---|---|---|---|
| 1 | **Model cost** | About $0.10 a learner a month (below), inside the $5 | About $500 a month for 5,000 learners | Batch API for the weekly reports: they aren't urgent, and batch pricing is typically about half (check whether Sumopod offers it). Prompt caching. Route simple questions to a smaller model. All through **LiteLLM Proxy**, which also does per-user budgets |
| 2 | **Provider rate limits and outages** | Not an issue | A Sunday batch of 5,000 reports hits limits; one provider outage stops everything | **LiteLLM Proxy:** retries, backoff, concurrency limits and a fallback provider, rather than our own client code |
| 3 | **The weekly burst** | One cron loop | 5,000 pipeline runs at 18:00 on Sunday | Runs become idempotent queue jobs keyed by (learner, week), spread across the evening in each learner's timezone. **Procrastinate**, a task queue on the Postgres we already run, so no new service. Temporal only if workflows grow much longer |
| 4 | **Database connections** | A handful | Every app and worker process holds connections | **PgBouncer** in transaction mode |
| 5 | **Dictionary reads** | Postgres alone | The same popular lookups, thousands of times a day | Cache dictionary tool results (never learner data) in **Valkey**, keyed by query. A read replica for `dict` if needed |
| 6 | **Sign-in** | Invite codes | Codes can't scale, and real accounts are needed | **Keycloak**, self-hosted. It supports OAuth 2.0 Token Exchange, so the delegation chain (ADR-018) can come from a real authorization server without changing the checks |
| 7 | **Abuse and bots** | Invite-only | Open sign-up attracts scripted abuse of a paid model | **Cloudflare** in front: rate limiting, plus Turnstile on sign-up |
| 8 | **Monitoring volume** | Grafana reading Postgres | Per-call rows grow fast, and dashboard queries slow the database | **The OpenTelemetry Collector** with tail sampling for traces; span metrics into **VictoriaMetrics**; Grafana stays |
| 9 | **Audit log volume** | JSONL files with a hash chain | Large files, and verification gets slow | Ship them with **Vector** to object storage. Keep the hash chain, and verify per day's segment |
| 10 | **Run inspection, prompt versions and evals on samples** | The Run Inspector page, prompts in git | Many prompt versions, and online evaluation on samples | **Langfuse** (open source, OpenTelemetry-compatible): traces, prompt versioning and scoring. It replaces the hand-built Run Inspector |
| 11 | **One server** | One small shared box | One failure takes everything down | The services are already stateless, so it's two app instances behind a load balancer, plus managed Postgres with point-in-time recovery. No code change |

## Things Arthur may not have accounted for

Some of these matter at ten learners too, so they are now in Phase 2
(marked **now**). The rest belong in the scale path.

| # | Gap | Why it matters | When | Off-the-shelf answer |
|---|---|---|---|---|
| 1 | **Data export (right of access)** | UU PDP gives people access to their data, not only deletion | **now** | No tool needed: an "Unduh data saya" button exporting the learner's rows as JSON |
| 2 | **Cross-border processing** | Questions go to a model provider outside Indonesia. UU PDP has rules on transfers abroad, so the consent notice must say so | **now** | Wording in the consent notice, and naming the provider on the "about" page |
| 3 | **A learner in distress** | Real people type real things into a chat. If someone writes about self-harm, Shiori needs a fixed, safe response, not improvisation | **now** | A moderation check before the model (the provider's moderation endpoint if Sumopod exposes it, otherwise a small local classifier). A fixed reply with Indonesia's official mental-health line (verify the number at build time). An alert to Arthur that contains no content |
| 4 | **Japanese input normalization** | Learners type romaji, half-width katakana and mixed forms, and without normalising, lookups miss | **now** | **jaconv** (width and kana conversion, romaji to kana) and **SudachiPy** (tokenizing and normalised forms) |
| 5 | **Fuzzy dictionary search** | "taberu", "食べる" and a typo should all find the word | **now**, as a Juku MCP tool | **pg_trgm**, and **PGroonga** for Japanese full-text search. Behind Juku's own `search_words` tool, because MCP-backbone's validator allows only built-in SQL functions |
| 6 | **Dictionary updates** | A learner's "known" words must survive data upgrades | **solved by reuse** | OpenJLPT's IDs are stable across releases; the upgrade script reports any that disappeared |
| 7 | **Timezones** | Indonesia has three (WIB, WITA, WIT), and some learners already live in Japan. "Sunday 18:00 WIB" is wrong for some of them | **now** | Store the learner's timezone (defaulting to WIB) and schedule in it |
| 8 | **Error tracking** | Exceptions get lost in logs | Should, now | **GlitchTip**, self-hosted and Sentry-compatible, so error data stays on our own server. Scrub content before sending |
| 9 | **Backups with point-in-time recovery, and restore drills** | A nightly dump loses a day of learners' work | Later; a nightly dump with a restore test now | **pgBackRest** |
| 10 | **Migrations without downtime** | Adding a column to a large table can lock it | Later; the habit now | Alembic with expand-and-contract, and **Squawk** to lint migrations in CI |
| 11 | **Secrets management** | Several services, keys rotated by hand | Now, small | **SOPS** with age, so secrets are encrypted in the repo, with keys held by Arthur |
| 12 | **Feature flags** | The Should features switch on mid-window (Phase 2) | Now, simple config | Config in `guardrails.yaml` now; **Unleash** at scale |
| 13 | **Status page and uptime checks from outside** | Our own heartbeat can't see a network outage | Later | **Uptime Kuma**, self-hosted |
| 14 | **Load testing** | The scale claims need one measurement | Should (below) | **Locust** (Python, like the rest) |
| 15 | **Streaming answers** | A 15 s wait feels broken; streamed text feels fast | Should, now | Server-sent events from FastAPI; nothing new to run |
| 16 | **More than one study group, or a school** | The natural next customer is a training centre preparing workers for Japan, with many classes | Later | The `cohort_id` exists from day one; per-cohort admin views later |
| 17 | **More interface languages** | Indonesian only, for now | Later | Babel / gettext, with the copy kept out of the templates from day one |

## Unit economics (estimates, from the cost model)

| Per active learner per month | Today's prices | With batch reports and caching |
|---|---|---|
| 4 weekly reports × $0.015 | $0.06 | ~$0.03 |
| ~8 chat questions × $0.005 | $0.04 | ~$0.03 |
| **Total** | **~$0.10** | **~$0.06** |
| **5,000 learners** | **~$500 a month** | **~$300 a month** |

The window measures the real cost per learner, and this table is then
re-stated from the records, with the estimate kept beside it.

## Anti-regression: fitness functions

The standard name for "designed so growth and change don't quietly undo
it" is **evolutionary architecture**. Its main tool is the **fitness
function**: an automated check that fails the build when a change
degrades a quality the design depends on (Phase 5, ADR-023). Juku has two
kinds:
- **deterministic ones**, which run in CI on every commit at $0;
- **the agent-quality regression gate**, from agent-eval-harness.

The harness gate's own published results show that at about 40 tasks it
missed some regressions it was expected to flag (its "not as expected"
rows). So Juku doesn't rely on it alone. The deterministic checks catch
what statistics at this sample size can't.

| # | Fitness function | Guards | Fails when | Runs |
|---|---|---|---|---|
| FF1 | **Query plans.** `EXPLAIN` on the hot queries (recommender, coverage, quiz pick, learner state) against a synthetic database of 5,000 learners | Scale | A sequential scan of `learning_events`, or a plan cost over its recorded ceiling | Every commit |
| FF2 | **Hot paths read summaries only** | Scale | A $0 page or an agent tool touches `learning_events` directly (checked from the query log in tests) | Every commit |
| FF3 | **Incremental state = full recompute** | Correctness | `learner_state` or `learner_coverage` differs from recomputing from events, on the fixtures | Every commit, and nightly in production |
| FF4 | **Migrations are safe** | Uptime at scale | Squawk flags a locking or rewriting migration | Every commit |
| FF5 | **MCP tool schemas are a contract** | Agents | A tool's name, description or input schema changed without its snapshot updated in the same commit. Schemas must stay strict-mode valid, the lesson from MCP-backbone and the upstream issue | Every commit |
| FF6 | **Prompt and context budgets** | Cost | A fixture report's or question's input tokens, counted offline with a tokenizer ($0), exceed their ceiling (say, 15k a question, 30k a report) | Every commit |
| FF7 | **Idempotent runs** | Reliability at scale | Killing a worker mid-run, then rerunning, duplicates or loses a weekly report | Every commit |
| FF8 | **Guardrails, delegation and isolation** | Security | Any test in G1, ID2 or M7 fails | Every commit |
| FF9 | **No content in records or traces** | Privacy | A planted question text shows up in per-call records, spans or the audit log | Every commit |
| FF10 | **Load** | Scale | The $0 path's p95 at N synthetic learners is worse than the recorded baseline by more than 20% | Before each release, and on demand (Locust, $0) |
| FF12 | **Frontend budget** (Lighthouse CI, mobile profile) | Speed on learners' phones | Over 100 KB of JavaScript on a page, or LCP > 2.5 s, INP > 200 ms or CLS > 0.1 | Every commit |
| FF11 | **Agent quality** (harness regression gate) | Quality | The harness reports a regression on the chat, memory or pipeline task sets | On every prompt, tool or model change, scripted parts at $0. The paid run needs Arthur's OK |

The thresholds are recorded in `guardrails.yaml`, next to the other
limits. Raising one is a visible, reviewed change, never a silent one.

## The load test (Should, $0)

- **What:** Locust drives 5,000 synthetic learners against the full stack
  on the laptop. The model is scripted (record and replay), so it costs
  nothing.
- **Measured:**
  - event writes per second;
  - the latency of the $0 pages;
  - the time to queue and run 5,000 weekly reports, with model latency
    simulated;
  - the time to verify the delegation chain per call;
  - database size and growth.
- **Published as:** "on one laptop-sized server, the non-model path
  handled N learners at p95 X ms". That is a measurement of the design,
  not a claim that 5,000 people have used it.
