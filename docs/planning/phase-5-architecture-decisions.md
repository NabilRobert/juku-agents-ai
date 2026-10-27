# Phase 5: Architecture Decisions

Short ADRs, 2026-10-27. **Settled** ones were decided with Arthur. The
rest are recommendations, open until he agrees (see the end).

```
                       ┌─────────────── gateway (auth, per-agent allow-lists, detection, audit) ───────────────┐
browser ─► Juku app ─┤                                                                                         │
 (thin)    (FastAPI)   ├─► MCP-backbone ─► dict DB (JMdict, KANJIDIC2, Tatoeba, JLPT lists; read-only login)   │
   ▲          │        └─► Juku MCP server (learner-scoped, read-only) ─► app DB (progress, memory) + dict DB │
   │          │                                                                                                 │
   │          ├─ chat agent "Shiori" ── tool loop ──► Sumopod (gpt-5-mini)
   │          └─ weekly pipeline (cron): facts (SQL) ─► Keiko (plan) ─► Tadashi ─► Nikki (report) ─► Tadashi ─► code approves
   │
   └── Arthur only: Grafana (tool and pipeline health, alerts), Run Inspector; traces to Project 6's Jaeger
```

### ADR-001: The users are Indonesian JLPT learners in a study group (settled)

**Decision:** adults preparing for N5–N2, recruited from a study group
Arthur joins as a member. He is studying Japanese himself; his use is
recorded separately.

**Why:**
- **Reach:** there are many open study groups, and Arthur has a genuine
  reason to be in one.
- **Weekly use:** studying is a habit, and the exam is a deadline.
- **Low-risk data:** the knowledge base is public; what is stored about
  learners is their study activity.
- **Database fit:** every output can be checked against the data.
- **Cost:** short interactions fit $5.

**Rejected:**
- *A developer community's resource directory:* a small, simple table and
  a weak reason to return.
- *A workplace data assistant:* needs an employer's OK, and its data could
  never be shown.
- *A local business's sales data:* confidential, so the evidence would be
  mostly redacted.

### ADR-002: Pitstop's pattern, applied to learning (settled)

**Decision:**
- Facts are computed in code.
- A small, named agent team works on a schedule; a critic reviews every
  output; code decides approval, with at most 2 revisions.
- Every run is recorded and inspectable.

**Why:**
- It's proven in Arthur's own work, and lessons carry over. Models are
  worst at arithmetic over tables, so they're given facts, not tables.
- It makes the portfolio a sequence: the same discipline, first on
  synthetic data, now with real users.

**Rejected:**
- *A single chat agent with no schedule:* nothing runs unattended, so
  there's nothing to show about reliability.
- *A free-form autonomous agent that decides its own steps:* it can't be
  checked, and its cost is unbounded.

### ADR-003: Open dictionaries in Postgres, served by MCP-backbone (settled)

**Decision:**
- JMdict, KANJIDIC2, KRADFILE/RADKFILE, Tatoeba and a community JLPT list,
  loaded by committed scripts into their own database.
- MCP-backbone serves it, on its own workspace and key, through a
  read-only login.

**Why:** it reuses Project 1 exactly as a stranger would, so every
dictionary query is validated, cost-checked, capped and audited.

**Rejected:**
- *Model memory:* the failure this project exists to measure.
- *A vector store over textbooks:* copyrighted, and not checkable.
- *Scraping an online dictionary:* terms of service, and no stable
  snapshot.

### ADR-004: A web page first, WhatsApp later (settled)

**Decision:** a small web page on Arthur's domain. WhatsApp report
delivery is a Could, after the window.

**Why:** no third-party approval, no phone numbers, and full control of
the consent, memory and deletion screens.

**Rejected:**
- *WhatsApp first:* business verification, a number, phone numbers as
  personal data, and per-conversation pricing.
- *Telegram:* less used in Indonesia, and not Arthur's second choice.

### ADR-005: A thin Python app with a hand-written tool loop

**Decision:**
- Python 3.12, FastAPI, server-rendered Jinja2 with a little TypeScript,
  SQLAlchemy and Alembic.
- An MCP Python SDK client to the gateway, and an OpenAI-compatible client
  to Sumopod.
- The tool loop and the pipeline are written by hand, so every call is
  recorded and traced.

**Why:** the loop is the subject being monitored, so it must be visible.

**Rejected:**
- *An agent framework (LangChain, LlamaIndex, CrewAI and the like):* it
  hides the loop being measured.
- *A single-page app:* more front end than this needs.
- *Direct database access from agents:* it skips the stack being shown.

### ADR-006: Juku's own MCP server, scoped by session, read-only

**Decision:**
- A small MCP server in this repo for the learner's data: progress,
  mistakes, memory, recommendations, reading sentences, plan and recent
  activity.
- The app mints a short-lived, signed token for one learner and one
  purpose (a chat session or one pipeline run), and the MCP session is
  opened with it.
- **No tool takes a learner ID.** Its database login reads only the
  progress and memory tables and the dictionary, and writes nothing.
- It sits behind the gateway, with its own allow-list entry per agent.

**Why:**
- A generic SQL tool over learner data would let an agent read anyone's
  rows if a prompt asked it to.
- Binding identity to the session puts isolation in the protocol layer,
  where a test can prove it (Phase 1, M7).
- It also gives a measured comparison between a generic tool
  (MCP-backbone's SQL) and purpose-built tools (Phase 1, F2).

**Rejected:**
- *Learner data through MCP-backbone:* one login per workspace, so there's
  no per-learner isolation.
- *Postgres row-level security behind MCP-backbone:* it would need a
  per-learner session variable that a generic SQL tool can't safely set.
- *Tools that take a learner ID:* isolation would then depend on the
  model passing the right one.
- *Giving agents write tools:* every write comes from a learner's click or
  from code that checks evidence (ADR-008).

### ADR-007: Four agents, with the critic's checks repeated in code

**Decision:**

| Agent | Input | Tools |
|---|---|---|
| Shiori (chat) | The learner's question | MCP-backbone read tools; Juku's server (this learner) |
| Keiko (planner) | The week's facts and the engine's candidates | Juku's server (this learner, this run) |
| Nikki (writer) | The facts and Keiko's approved plan | none |
| Tadashi (critic) | An output and exactly what its author was given | none |

- The weekly pipeline runs per active learner: facts → Keiko → Tadashi →
  Nikki → Tadashi.
- Tadashi lists each issue with a severity. An output passes only if there's
  no high-severity issue (Phase 2, AG1).
- **Code runs the high-severity checks itself too:**
  - every number is in the facts;
  - every word ID is among the candidates and at the stated level;
  - citations exist;
  - nothing is contradicted by newer activity;
  - notes are in an allowed category.

  So the critic can miss something without a bad report going out.
- After 2 revisions, a facts-only template report is published instead,
  and counted.
- The names are puns on each job, chosen with Arthur (Phase 1). The
  deterministic recommender is called Susumu.

**Why:** this is Pitstop's critic, with one lesson applied: "code decides
approval" now also covers the checks a model can miss.

**Rejected:**
- *No critic:* nothing would catch the claims code can't check, such as a
  misleading explanation.
- *An LLM critic alone:* it can miss a wrong number, and that's the cheap
  thing to check in code.
- *More agents (a separate analyst, say):* more cost per report for little
  gain, since the analysis is SQL.

### ADR-008: Memory is structured, inspectable and evidence-backed (settled)

**Decision:**
- **Three kinds, in Postgres:**
  - what the learner knows, always recomputed from activity;
  - what happened, the activity rows;
  - agent notes.
- **Agents only propose notes,** each with a category and the IDs of the
  activity rows behind it. Code stores a note only if:
  - its category is allowed (learning only);
  - its evidence belongs to this learner;
  - the evidence actually shows the pattern.
- **Consolidation each week:** what is known is recomputed, and a note
  lapses once its evidence is over 30 days old and hasn't recurred.
- **The learner sees every item** with its evidence, and can remove it or
  mark it wrong.
- **Measured:** memory tasks in the categories memory benchmarks use
  (LongMemEval, LoCoMo): a fact that changed, time, and abstention.
  Also measured: rejected proposals, corrections by learners, and stale
  claims (Phase 1, MEM1–MEM5).

**Why:**
- Long-term memory is a central agent topic in 2026. Its weak point is
  opacity: users can't see or fix what an agent believes about them.
- Structured memory with evidence can be inspected and tested, and
  deleting it actually deletes it, which also covers the privacy duties.

**Rejected:**
- *A vector-store memory (embeddings of past chats):* opaque, hard to
  delete precisely, and it can't show its evidence.
- *A memory framework (Mem0, Letta and the like):* another service on a
  small server, and its memory decisions would be the framework's, not
  checkable rules.
- *Letting agents write notes directly:* a wrong inference about a person
  would be stored without any check.

### ADR-009: Monitoring is Grafana over Postgres, with alerts

**Decision:**
- **Records:**
  - per-call records for every MCP call, per agent and per server;
  - the run records;
  - the gateway's audit log, imported after its hash chain is verified;
  - MCP-backbone's audit log, read through a read-only role.

  All of it in a `monitoring` schema.
- **Dashboard:** one Grafana OSS container, with a Postgres data source
  on a read-only role. Dashboards and alert rules are provisioned from
  committed files; loopback only, behind Arthur's login, capped at
  256 MB. No panel can show one learner.
- **Alerts:** a heartbeat (the dead-man's switch), missed scheduled runs,
  budget thresholds, error rates, detector flags, a broken audit chain,
  and refused cross-learner attempts. They go to Arthur only.
- **Traces:** to Project 6's Jaeger, with the trace ID in each per-call
  record.

**Why:** Project 6 deliberately stops at traces, and the health of the
tools and agents is this project's subject. Grafana reading Postgres is
one service with no metrics pipeline, and its numbers come from the same
tables as the evidence SQL.

**Rejected:**
- *Prometheus + Grafana:* two services and a metrics endpoint in each
  project.
- *Jaeger's span metrics:* it needs Prometheus too, and Project 6 lists it
  as future work.
- *A hosted monitoring service:* another account, and data leaving the
  server.
- *Cron alerts only:* the fallback if Grafana's memory doesn't fit
  (spike 3).

### ADR-010: The learning engine is deterministic code

**Decision:**
- **Known words, coverage, quizzes (generation and grading), the pace
  planner and the Leitner mistakes queue** are SQL and Python, pinned by
  fixture learners (Phase 1, E1).
- **The recommender: i+1 with kanji leverage.**
  - **Precomputed tables:** `word_kanji`; `word_level` (level, tier,
    frequency band); `kanji_leverage` (how many common words at or below
    each level contain the kanji).
  - **Known kanji:** every kanji of the easier levels, plus those in words
    the learner knows.
  - **Candidates:** words at the learner's level or easier, not known, with
    at most one unknown kanji. Kana-only words qualify.
  - **Ordering, lexicographic with no tuned weights:**
    1. common words first;
    2. gaps from easier levels first;
    3. the leverage of the unknown kanji, higher first;
    4. the frequency band;
    5. the entry ID, for determinism.
  - **Variety:** at most 3 of 10 suggestions share a new kanji.
  - **Reason:** built from the row, for example "1 kanji baru: 日, muncul
    di 34 kata umum N5".
  - **Frozen during the window.** It may be tuned once beforehand. A later
    change is a "what changed", with before and after.
- **Reading practice (Should):** Tatoeba sentences whose indexed words are
  all known except one.

**Why:** explainable, testable to the exact row, and free. Agents add
judgement and explanation on top, and never invent the facts.

**Rejected:**
- *Model-generated suggestions or quizzes:* not checkable, they cost
  money, and they vary run to run.
- *Collaborative filtering:* needs far more learners, and it builds
  profiles of people.
- *Full spaced repetition (SM-2):* a large feature. Leitner boxes cover
  the mistakes queue.

**Known risk:** JLPT lists name words by spelling, which can match several
JMdict entries. The mapping rules and the unresolved count are reported
(spike 4).

### ADR-011: gpt-5-mini through Sumopod

**Decision:** gpt-5-mini for all four agents, with the lowest reasoning
effort that keeps Q1 ≥ 90% and MEM1 ≥ 90%, chosen in slice 7.

**Why:** measured on this stack: 95.5% and 96.0% strict over Pagila, at
about $0.0027 a question, with a 13 s median.

**Rejected:**
- *gpt-5-nano by default:* 91.0%, and a slower median (27 s). It stays a
  Could, as a measured fallback.
- *gemini-3.5-flash:* six times the input price.

### ADR-012: Spend is capped in three layers, in two pools

**Decision:**
1. **The app's budget guard,** checked before every model call. It has two
   pools:
   - **reports** are reserved, so chat can't starve them;
   - **chat** has per-learner and global daily caps, and a hard stop.
2. **The gateway** limits what agents can do (allow-lists, no writes). A
   per-key rate limit is a Should, built in the gateway repo.
3. **The Sumopod key cap**, about $4.50: the backstop.

**Why:** the key cap alone stops abruptly, mid-run, with an error. The
guard stops cleanly and explains, and the $0 features keep working.

**Rejected:**
- *The key cap alone:* see above.
- *One shared pool:* a busy week of chat could cancel everyone's report.

### ADR-013: Invite codes and nicknames, no email

**Decision:** one random code per person, issued by Arthur. Only its hash
is stored, plus a nickname.

**Why:** the least personal data that still bounds access and cost.

**Rejected:**
- *Google sign-in, or email magic links:* they store email addresses.
- *Open sign-up:* unbounded cost and abuse.

### ADR-014: Scheduling is external cron, with a dead-man's switch

**Decision:** a crontab entry starts the weekly pipeline (Sunday 18:00
WIB) and the nightly consolidation and audit import. Each run records its
start and end, and an alert fires if a due run hasn't completed within an
hour.

**Why:** it's what Pitstop did. The app has no scheduler inside it, so
"no crontab" means "no runs", which is easy to check.

**Rejected:**
- *A scheduler inside the app (APScheduler, Celery beat):* runs can stop
  silently when the app restarts.
- *A hosted scheduler:* another account.

### ADR-015: Quality is measured offline first, then in a closed loop

**Decision:**
- **Offline:**
  - about 40 chat tasks;
  - about 15 memory tasks;
  - pipeline fixtures for 10 learners.

  All are in agent-eval-harness, written in Indonesian, with gold answers
  from SQL over fixture data; strict scoring, pass^k reported. The launch
  gate is Q1 ≥ 90% and MEM1 ≥ 90%.
- **Online:**
  - the citation check on every answer;
  - the code checks on every report;
  - Arthur's weekly hand checks against committed rubrics;
  - learners' ratings.
- **The loop:** weekly, any failure category seen 3 or more times becomes
  a task or fixture, then a fix, then a rerun. A learner's words go into a
  task only with that message's quote permission; otherwise the task is
  paraphrased.
- **Evidence:** committed SQL over the records, as in Pitstop.

**Rejected:**
- *A model as judge for headline numbers:* it costs budget, and it's
  another unverified claim.
- *Ratings alone:* too few and too biased.

### ADR-016: Hosting is Docker Compose on the shared server

**Decision:**

| Container | Contents | Memory cap |
|---|---|---|
| `app` | FastAPI app and pipeline workers. Non-root, read-only filesystem, `cap_drop: ALL` | 256 MB |
| `juku-mcp` | Juku's MCP server | 128 MB |
| `db` | `postgres:16` with two databases: `app` (progress, memory, records, `monitoring`) and `dict`. Each login reaches only what it needs | 384 MB |
| `grafana` | Grafana OSS, provisioned from files | 256 MB |

- Only `app` and `grafana` are reached from outside, through the server's
  existing proxy.
- The gateway and MCP-backbone run as they already do. Placing the gateway
  in front of both MCP servers for this app is a server step done by
  Arthur or the server session.

**Why:** isolated from the other projects' data, capped, and the same
pattern as the Pitstop demo.

**Rejected:**
- *Separate Postgres containers:* about 100 MB more, for isolation that
  roles already give.
- *Using MCP-backbone's own Postgres:* it would share a cluster with
  MCP-backbone's key data.

### ADR-017: A fixed window, and results reported as they are (settled)

**Decision:** the window is the first 4 counted weeks after launch, with
metrics, floors and rubrics committed beforehand. If adoption misses, the
case study says so and what was learnt. The window isn't stretched, and
Arthur isn't counted.

**Why:** credible real-use numbers are the point.

### Later (Could), recorded so they aren't re-decided

- **The text speaking partner (X3):**
  - Japanese role-play that keeps to known words plus one new word a turn,
    checked by a tokenizer in code;
  - text only, because voice recordings are sensitive and costly;
  - built only if spend is under plan at week 2.
- **A quiz as an MCP App (X4):** inside a learner's own assistant. It
  needs OAuth on Juku's MCP server; after the window.
- **The group digest (X1) and WhatsApp delivery (X2):** after the window.

## Open for Arthur

| # | Decision | Recommendation |
|---|---|---|
| 1 | The repo name | `jlpt-learning-agents` |
| 3 | The alert contact point (ADR-009) | A Telegram bot that messages only you |
| 4 | Grafana or cron-only monitoring (ADR-009) | Grafana, if spike 3's idle memory fits |
| 5 | The gateway's per-key rate limit (ADR-012) | Build it in the gateway repo before launch |
| 6 | Launch timing against the December JLPT | Don't rush. If it's ready after about 20 November, run December as an uncounted soft launch, and start the counted window in early January towards the July 2027 exam |
