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

### Reuse map (the folder's "reuse before building" rule)

| Part | Reused | Built (and why) |
|---|---|---|
| Data | **OpenJLPT** (ADR-003); its PyPI package for search | The load script only |
| Dictionary access | **MCP-backbone** (Arthur's) | — |
| Auth, allow-lists, audit, injection detection | **mcp-security-gateway** (Arthur's) | The per-agent policy file |
| Offline evals and the regression gate | **agent-eval-harness** (Arthur's) | The Juku task sets |
| Traces | **agent-observability** (Arthur's, Project 6), OpenTelemetry | — |
| The critic pattern | **Pitstop** (Arthur's), ported from TypeScript (ADR-007) | The Python port |
| Dashboards and alerts | **Grafana OSS** (ADR-009) | Provisioned dashboards and alert rules |
| Hosting, TLS, scheduling | Docker Compose, Caddy, cron | Compose and crontab files |
| Japanese input | **SudachiPy**, **jaconv** | — |
| The learner's MCP server | The MCP Python SDK | The scoped tools: no existing server holds Juku's learner data |
| Delegation tokens | RFC 8693 claim shapes; Keycloak at scale | A small signer and verifier (ADR-018) |
| Learning engine and Susumu | — | Built: deterministic, testable logic over Juku's data is what's demonstrated (ADR-010) |
| The agents and the tool loop | **PydanticAI** (ADR-005, ADR-025) | The agents' prompts, tools and typed outputs |

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

### ADR-003: OpenJLPT as the data, in Postgres, served by MCP-backbone (settled; revised 2026-10-28)

**Decision:**
- **The data is [OpenJLPT](https://github.com/evanclan/OpenJLPT):**
  - 7,811 words, 2,383 kanji and **526 grammar points**, N5–N1;
  - 99.7% of its words are linked to their JMdict entry;
  - Tatoeba example sentences with furigana for 93% of words;
  - kanji readings, radicals, stroke counts and frequency (from
    KANJIDIC2);
  - stable IDs that survive data updates.

  It is CC BY-SA 4.0, with per-field attribution.
- **A pinned release is loaded** (version and checksum recorded) from its
  SQLite file into Juku's own Postgres database by a committed script.
- **MCP-backbone serves it,** on its own workspace and key, through a
  read-only login. Fuzzy word search ("taberu", "食べる", a typo) uses
  OpenJLPT's own Python package (`pip install openjlpt`, ranked search
  over kanji, kana, romaji and English), behind Juku's MCP server's
  `search_words` tool, instead of a search index we build ourselves.
- **Arthur's textbook PDFs are a private coverage checklist,** never a
  source of text. They're used only to spot topics or words OpenJLPT
  lacks. They're never committed, never sent to a model, and no text is
  copied from them.
- **Licence duties:**
  - the "about the data" page carries OpenJLPT's attribution (OpenJLPT,
    built on JMdict and KANJIDIC2 from the EDRDG, Jonathan Waller's JLPT
    lists and Tatoeba);
  - any dataset Juku derives from it and redistributes is also CC BY-SA
    4.0. Juku's code licence is separate.

**Options considered** (the folder's "reuse before building" rule):

| Option | Verdict |
|---|---|
| **OpenJLPT** | **Chosen.** It already does the hard, error-prone part of this project's data work: mapping community JLPT lists to JMdict (the job spike 4 was measuring), with hundreds of source errors fixed. It adds 526 reviewed grammar points we would otherwise have had to write. It ships SQLite, JSON, CSV, npm and PyPI packages |
| Raw JMdict + KANJIDIC2 + KRADFILE + Tatoeba, with our own mapping | Rejected as the primary source: more loading code, and the level mapping redone by hand. A full JMdict import stays a **Could**, for words outside the JLPT lists |
| Hand-written grammar explanations | Rejected: OpenJLPT's are written and reviewed already |
| Textbook content as data | Rejected: copyrighted. The PDFs stay a private checklist only |
| A vector store over textbooks | Rejected: copyrighted, and not checkable against rows |
| Scraping an online dictionary | Rejected: terms of service, and no stable snapshot |
| Model memory | Rejected: the failure this project exists to measure |

**Why:** it reuses Project 1 exactly as a stranger would, so every query is
validated, cost-checked, capped and audited, over data someone else has
already cleaned and licensed correctly.

**Risk, and its mitigation:** OpenJLPT is young and effectively has one
maintainer (release v0.2.0, July 2026). It's rebuilt from public sources
by published scripts, so a pinned release keeps working even if the
project stops. If it does stop, its scripts can be rerun, or the raw
sources loaded directly.

**What it changes:**
- **Grammar questions** can now be answered from OpenJLPT's grammar
  points, with citations, which narrows the N2 grammar gap (Phase 1).
- **Susumu** uses OpenJLPT's kanji frequency, levels and word lists
  (ADR-010).
- **Reading practice** uses OpenJLPT's example sentences, tokenized with
  SudachiPy (Phase 2, LE4).
- **Stable IDs** settle the dictionary-update concern in the scale path.

### ADR-004: A web page first, WhatsApp later (settled)

**Decision:** a small web page on Arthur's domain. WhatsApp report
delivery is a Could, after the window.

**Why:** no third-party approval, no phone numbers, and full control of
the consent, memory and deletion screens.

**Rejected:**
- *WhatsApp first:* business verification, a number, phone numbers as
  personal data, and per-conversation pricing.
- *Telegram:* less used in Indonesia, and not Arthur's second choice.

### ADR-005: A thin Python app, with PydanticAI for the agents (revised 2026-10-28)

**Decision:**
- Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, Pydantic, Typer, uv.
  Pages are server-rendered shells with Vue islands (ADR-024).
- **The agents run on PydanticAI** (approved by Arthur 2026-10-28,
  ADR-025):
  - its MCP client reaches the gateway over Streamable HTTP;
  - its OpenAI-compatible provider reaches Sumopod;
  - typed outputs carry Tadashi's issues and Keiko's note proposals;
  - `UsageLimits` caps each run;
  - `TestModel` and `FunctionModel` drive the $0 scripted tests;
  - its OpenTelemetry instrumentation feeds Project 6.
- **The pipeline is PydanticAI agents chained in plain Python,** in a fixed
  order (ADR-007).

**Why:** the loop is the subject being monitored, so it must be visible.
PydanticAI keeps it visible: every message and tool call is in the run's
message history and its spans. It also removes the loop code we would
otherwise have written and tested ourselves.

**Rejected:**
- *A hand-written loop* (this ADR as first written): it reimplements what
  the framework does, against the folder's "frameworks over plain code"
  rule.
- *LangChain, LlamaIndex, CrewAI:* heavier, and they hide the loop being
  measured.
- *The OpenAI Agents SDK:* close, but tied to OpenAI's conventions, with
  less emphasis on typed outputs.
- *A single-page app:* more front end than this needs (ADR-024).
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
  from code that checks evidence (ADR-008). The one action tool,
  `request_replan`, only queues a run whose result still passes the
  critic and code (ADR-018).

### ADR-007: Four agents, with the critic's checks repeated in code

**Decision:**

| Agent | Input | Tools |
|---|---|---|
| Shiori (chat) | The learner's question | MCP-backbone read tools; Juku's server (this learner), including `request_replan` |
| Keiko (planner) | The week's facts and the engine's candidates | Juku's server (this learner, this run) |
| Nikki (writer) | The facts and Keiko's approved plan | none |
| Tadashi (critic) | An output and exactly what its author was given | none |

- The weekly pipeline runs per active learner: facts → Keiko → Tadashi →
  Nikki → Tadashi.
- **Code orchestrates the crew**, in a fixed order. No agent decides which
  agent runs next.
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

**Reused:** Pitstop's critic design: severities, code-decided approval,
at most 2 revisions, and the weekly feedback job. It lives in Arthur's own
public repo (`gads-case-study`, `backend/src/pipeline/`). That code is
TypeScript and Juku is Python, so the rules are ported, not depended on,
and the commit that ports them names the source repo and commit.

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
  - **Precomputed tables, built from OpenJLPT (ADR-003):**
    - `word_kanji`: each word's kanji;
    - `word_level`: OpenJLPT's level, plus a commonness rank taken from
      the KANJIDIC2 frequency of the word's rarest kanji (OpenJLPT has no
      word frequency; kana-only words count as common);
    - `kanji_leverage`: how many words at or below each level contain the
      kanji.
  - **Known kanji:** every kanji of the easier levels, plus those in words
    the learner knows.
  - **Candidates:** words at the learner's level or easier, not known, with
    at most one unknown kanji. Kana-only words qualify.
  - **Ordering, lexicographic with no tuned weights:**
    1. gaps from easier levels first;
    2. the leverage of the unknown kanji, higher first;
    3. commonness (the kanji-frequency rank), most common first;
    4. OpenJLPT's stable ID, for determinism.

    If a full JMdict import is added later (a Could), its priority tags
    could become a "common words first" step.
  - **Variety:** at most 3 of 10 suggestions share a new kanji.
  - **Reason:** built from the row, for example "1 kanji baru: 日, muncul
    di 34 kata umum N5".
  - **Frozen during the window.** It may be tuned once beforehand. A later
    change is a "what changed", with before and after.
- **Reading practice (Should):** OpenJLPT's example sentences (from
  Tatoeba, with furigana), tokenized with SudachiPy and matched to word
  IDs. A sentence qualifies when every word in it is known except one.

**Why:** explainable, testable to the exact row, and free. Agents add
judgement and explanation on top, and never invent the facts.

**Rejected:**
- *Model-generated suggestions or quizzes:* not checkable, they cost
  money, and they vary run to run.
- *Collaborative filtering:* needs far more learners, and it builds
  profiles of people.
- *Full spaced repetition (SM-2):* a large feature. Leitner boxes cover
  the mistakes queue.
- *An existing i+1 tool such as the AnkiMorphs (MorphMan) add-on, or
  OpenJLPT's own flashcards:* they run in the learner's Anki or browser,
  not behind an MCP server, so they can't be audited, traced or tested as
  part of the stack. A deterministic ranking that *can* be is what this
  project demonstrates, so building it is the point.

**Known risk:** JLPT levels are community approximations (Jonathan
Waller's lists, via OpenJLPT), and about 0.3% of OpenJLPT's words aren't
linked to JMdict. Spike 4 reports the unlinked count and how they're
handled.

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

### ADR-015: Evaluation-driven development: tasks first, then a closed loop

**Decision:**
- **Tasks before agents.** Each agent's eval tasks and fixtures are
  committed before its code, and fail against a stub. The agent is then
  built until they pass. Git history shows the order (Phase 1, EDD1). The
  same holds for each guardrail: its test comes first.
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
- *Writing the evals after the agent works:* the tasks would then be
  shaped by what the agent already does.

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

### ADR-018: Agent identity and delegated authorization, in a small testable form

**Decision:**
- **Each agent is its own identity:** its own gateway key and allow-list.
  No key is shared.
- **Every call carries a delegation chain.** It is a short-lived token,
  signed by the app, with claims modelled on OAuth 2.0 Token Exchange
  (RFC 8693):
  - the learner, pseudonymous, as the subject;
  - the nested `act` chain of agents;
  - the purpose and run;
  - the allowed tools;
  - the audience (the Juku MCP server);
  - the expiry.

  It travels in the MCP request's `_meta`, never as the gateway's
  credential.
- **Delegation only narrows.** The one multi-hop path is learner → Shiori
  → (`request_replan`) → Keiko → Juku MCP server. Each hop:
  - may only drop tools;
  - may only shorten the expiry;
  - keeps the same learner.

  More than 2 agent hops is refused.
- **Checked at both ends:** the Juku MCP server verifies the whole chain.
  The gateway checks (Should, in the gateway repo) that the chain's last
  actor is the agent whose key made the call.
- **Visible:** every hop is logged with its chain, and the learner's "who
  accessed my data" page lists agent, tool and time.
- **Before fixing the details,** spike 6 reads the MCP authorization spec
  current at build time. Arthur notes that a July 2026 revision tightened
  it.

**Why:**
- "Who is this agent, and what may it do for whom" has no settled standard
  yet, and multi-hop delegation is the unsolved part.
- Juku has a real multi-hop path, small enough to make every rule
  testable: narrowing, expiry, depth, audience, replay, actor binding.
- Using RFC 8693's shape means the tokens could later come from a real
  authorization server without changing the checks.

**Rejected:**
- *One app key for all agents:* the audit log couldn't say which agent
  acted.
- *Long-lived keys per learner:* they can't express purpose or narrowing,
  and they're hard to revoke cleanly.
- *A full OAuth authorization server now:* another service to run and
  secure, for a single app. The claims are shaped so one can replace the
  app's signer later.
- *An agent-to-agent protocol (A2A) between the crew:* they run in one
  process. A chain inside the MCP call is enough, and it's easier to test.
- *Waiting for a standard:* the problem exists now, and a small, tested
  version is the portfolio point.

### ADR-019: Guardrails are code with tests, in one rule file

**Decision:**
- Every limit lives in a committed rule file (`guardrails.yaml`), or in
  the gateway's policy file for tools. That covers spend caps, data scope,
  delegation depth, allowed memory categories, report checks and privacy
  floors.
- Code reads it at start-up. Each rule has a test that fails when the rule
  is removed (mutation-checked).
- The table in Phase 2 maps each rule to where it's enforced and how it's
  tested.

**Why:** the move is from policy documents to limits enforced in code.
One file makes the governance readable, and the tests make it true.

**Rejected:**
- *Rules described in docs only:* nothing checks them.
- *A guard model as the main line of defence:* one more probabilistic
  claim. The gateway's detector is one layer; the hard limits are code.
- *Rules scattered as constants:* they can't be read or reviewed as a
  whole.

### ADR-020: A safety eval on Juku's own attack surfaces

**Decision:**
- About 15 attack tasks:
  - injection planted in a fixture copy of Tatoeba sentences;
  - cross-learner reads;
  - planting false or forbidden memory through chat;
  - widening a delegation;
  - calling a tool outside an agent's list.
- The prediction is committed first. The suite is run with the gullible
  scripted agent, with and without the gateway ($0), then once with the
  real model (about $0.12, with Arthur's OK).

**Why:** agent safety is the fastest-growing agent research topic. Juku
has real surfaces: Tatoeba is written by the public, and memory and
delegation are new attack paths. It reuses the gateway project's method,
so the two results can be read together.

**Rejected:**
- *Reusing the gateway's generic suite only:* it doesn't touch memory or
  delegation.
- *Planting attacks in the live data:* real learners would see them.

### ADR-021: Memory, not continual learning (settled)

**Decision:**
- Juku claims memory: facts about each learner, with evidence, that the
  learner can inspect.
- It doesn't claim continual learning. The models' weights never change,
  and "learning from feedback" means the feedback job drafting prompt
  changes that Arthur approves.

**Why:** continual learning is still research, and claiming it would
overstate the work to the audience this portfolio is for.

### ADR-022: Built for ten, designed for thousands

**Decision:**
- **Now:** only what is cheap today and expensive to change later. That
  means the data design in the [scale path](scale-path.md):
  - a narrow event table, partitioned by month;
  - incremental summaries;
  - text apart from metrics, with expiry;
  - `cohort_id`, timezones, `bigint` keys with random public IDs;
  - stateless services;
  - idempotent runs.
- **Later:** growth uses existing tools, not our own builds. That covers:
  - LiteLLM Proxy for cost, limits and fallbacks;
  - Procrastinate for the weekly queue;
  - PgBouncer, Valkey, Keycloak, Cloudflare, the OpenTelemetry
    Collector with VictoriaMetrics, Vector, and Langfuse.

  Each is named against the bottleneck it answers.
- **The only scale claim** is the load test ($0, scripted model), stated
  as a measurement of the design.

**Why:**
- Evaluators ask "would this survive growth?". The honest answer is a
  data design that already would, and a named path for the rest.
- The pressure at scale is model cost and provider limits, not data. The
  doc says so with unit economics: about $0.10 a learner a month now, and
  about $0.06 with batch reports and caching.

**Rejected:**
- *Building the scaled stack now:* more services than a small shared
  server should run, for users who don't exist yet.
- *Ignoring scale:* the data design is a one-way door, and changing it
  later means migrating real learners' history.
- *Building our own queue, model proxy or auth server:* mature tools
  exist, and owning them is the wrong use of the time.

### ADR-023: Anti-regression by fitness functions, plus the harness gate

**Decision:**
- **Deterministic fitness functions** in CI on every commit, at $0:
  - query plans on a synthetic 5,000-learner database;
  - hot paths reading summaries only;
  - incremental state matching a full recompute;
  - migration linting;
  - MCP tool schemas as snapshot contracts, kept strict-mode valid;
  - prompt and context token ceilings, counted offline;
  - idempotent runs;
  - the guardrail, delegation and isolation suites;
  - no content in records or traces.
- **Before releases:** a load-test comparison.
- **For agent quality:** the harness regression gate, on every prompt,
  tool or model change.
- Thresholds live in `guardrails.yaml`, so raising one is a reviewed
  change.

**Why:**
- "Evolutionary architecture" is the name for designing so change doesn't
  quietly undo the design. Fitness functions are how it's enforced.
- The harness gate, by its own published results, missed some expected
  regressions at about 40 tasks. Deterministic checks catch what
  statistics at that size can't.
- The tool-schema contract carries over the lesson of the upstream
  strict-schema issue.

**Rejected:**
- *Relying on the harness gate alone:* too little statistical power at
  this size.
- *Manual review only:* it doesn't scale, and it misses slow drift.
- *Load tests on every commit:* too slow. They run before releases.

### ADR-024: The frontend is server-rendered, lazy, and held to a budget (revised 2026-10-28)

**Decision:**
- Jinja2 page shells, with **Vue 3 + TypeScript islands** mounted only
  where a page is interactive (chat, quiz, the memory page). There's no
  client router. Approved by Arthur 2026-10-28 (ADR-025), so the frontend
  matches his stack. Vitest for tests.
- Vite building one small bundle per page, with dynamic imports for the
  heavy pieces.
- Lazy images, and lists loaded 20 at a time.
- System fonts for Japanese, and `<ruby>` for furigana.
- Tailwind, with unused classes stripped.
- Caddy's compression and immutable caching.
- **The budget:** ≤ 100 KB of JavaScript per page; LCP ≤ 2.5 s, INP ≤ 200 ms
  and CLS ≤ 0.1 on mobile. Enforced by Lighthouse CI (FF12), and watched
  in real use through `web-vitals` sent to our own endpoint.

**Why:**
- The learners are on mid-range Android phones and mobile data.
- Server-rendered pages are fast on first load, and the app is thin by
  design.
- A Japanese web font alone can be several megabytes; system fonts cost
  nothing.
- A budget checked in CI is the same anti-regression idea as the fitness
  functions.

**Rejected:**
- *htmx* (this ADR as first written): small, but not in Arthur's stack.
- *A full Vue or React single-page app:* a large first download and client
  routing, for a handful of simple pages.
- *Next.js or Nuxt:* a second runtime (Node) next to the Python app, for
  no gain here.
- *A full Japanese web font:* megabytes, for glyphs the phone already has.
- *A third-party real-user monitoring service:* data leaving our server.

### ADR-025: A framework for every component (the folder's "frameworks over plain code" rule)

Default to Arthur's stack: FastAPI, Pydantic, SQLAlchemy 2 + Alembic,
Typer, pytest, uv, ruff and pyright, the MCP SDK, Vue 3 / TypeScript /
Tailwind / Vite / Vitest, the OpenTelemetry SDK and Inspect AI. Rows
new to his stack were proposed and **approved by Arthur on 2026-10-28**
(PydanticAI, Vue islands, and all the small libraries).

| Component | Framework (recommended) | Why | Rejected alternative | Status |
|---|---|---|---|---|
| **Agent loop** (Shiori, Keiko, Nikki, Tadashi) | **PydanticAI** | Its MCP client connects to the gateway over Streamable HTTP. It speaks to Sumopod through its OpenAI-compatible provider (a base URL). Typed outputs (Pydantic models) suit Tadashi's issues and Keiko's note proposals. `UsageLimits` caps tokens and requests per run, which backs the budget guard. `TestModel` and `FunctionModel` give the $0 scripted runs. OpenTelemetry instrumentation follows the GenAI conventions Project 6 uses. Every message and tool call stays visible in the run's message history, so the "loop must be visible" reason in ADR-005 still holds | A hand-written loop (ADR-005 as first written): it reimplements what the framework does. LangChain and LlamaIndex: heavier, and they hide the loop. *Spike 6 checks that the delegation token can be set in each call's `_meta`* | **approved 2026-10-28** (ADR-005 revised) |
| **The crew's orchestration** (the weekly pipeline) | PydanticAI agents chained in plain Python: its documented "programmatic hand-off" pattern | A fixed 4-step chain with at most 2 revisions is a few lines; code decides the order (ADR-007) | pydantic-graph, a state-machine framework: heavier than a fixed chain | with the row above |
| **Scheduling** | **cron starting a Typer CLI command** (`juku run-weekly`, `juku consolidate`, `juku import-audit`) | The OS scheduler plus Arthur's CLI framework, as Pitstop did; "no crontab = no runs" stays checkable; the dead-man's switch watches the records (ADR-014) | APScheduler, in-process: jobs stop silently when the app restarts, and run twice with two workers. At scale, Procrastinate (scale path) | stack (Typer); cron is the OS |
| **HTTP API and pages** | FastAPI, with Jinja2 for the page shells | Arthur's stack; MCP-backbone's console does the same | — | stack |
| **Interactive frontend** (chat, quiz, memory page) | **Vue 3 + TypeScript + Tailwind + Vite, as per-page "islands"**: the server renders the page, Vue mounts only the interactive parts, and there's no router; Vitest for tests | Arthur's frontend stack, so it looks like one team's work. The Vue runtime (~30 KB compressed) fits the 100 KB per-page budget (ADR-024, FF12) | htmx (ADR-024 as first written): not in his stack. A full Vue SPA with a router: a heavier first load | **approved 2026-10-28** (ADR-024 revised) |
| **Streaming answers** | sse-starlette | Server-sent events for FastAPI, done properly (disconnects, pings) | A hand-written `StreamingResponse` event format | small library |
| **Settings, and the rule file** (`guardrails.yaml`) | Pydantic Settings and Pydantic models | Validated at start-up; a bad limit fails loudly | Reading the YAML into plain dicts | stack |
| **Database and migrations** | SQLAlchemy 2 + Alembic; Postgres's own partitioning (pg_partman at scale) | Stack | — | stack |
| **Juku's MCP server** | The official MCP Python SDK | Stack; the same as MCP-backbone | — | stack |
| **Delegation tokens** (ADR-018) | **PyJWT** with Ed25519 (`cryptography`) | Well-maintained JWT signing and checking; RFC 8693's `act` claim is just a nested claim | Hand-rolled signed tokens; Authlib (more than needed); Keycloak now (scale path) | **approved 2026-10-28** |
| **Login sessions and invite codes** | Starlette's `SessionMiddleware` (signed cookies) and **argon2-cffi** for code hashes | No hand-rolled cookies or hashing | passlib (unmaintained); plain SHA-256 for codes | **approved 2026-10-28** |
| **HTTP calls and retries** (non-model) | **httpx** and **tenacity** | The established choices; PydanticAI already retries model calls | `requests` plus hand-written retry loops | **approved 2026-10-28** |
| **Structured logs** | **structlog** | JSON logs with request and trace IDs, alongside OpenTelemetry | `logging` with hand-formatted JSON | **approved 2026-10-28** |
| **Japanese input** | SudachiPy, jaconv; OpenJLPT's package for search | Reuse (ADR-003) | — | **approved 2026-10-28** |
| **Moderation** (Phase 2, AG6) | The provider's moderation endpoint through the same OpenAI-compatible client; if Sumopod doesn't expose one, a small local classifier on the gateway's ONNX setup | No hand-written keyword lists | A keyword blocklist | to check in a spike |
| **The WhatsApp channel** (Could, X2) | **The WhatsApp Cloud API through `pywa`**: a Python framework for Meta's official API, with FastAPI webhook support | Official API, so no ban risk; it fits the FastAPI app | Twilio for WhatsApp (an extra account and per-message fee on top of Meta's); unofficial WhatsApp Web libraries (against WhatsApp's terms; numbers get banned) | **approved 2026-10-28**, for after the window |
| **CLI** (load, export, delete, runs) | Typer | Stack | argparse | stack |
| **Tests** | pytest (+ mutmut), Vitest, Lighthouse CI, Locust | Stack, plus the tools the fitness functions name | — | stack |
| **Evals** | Inspect AI, via agent-eval-harness | Stack | — | stack |
| **Tracing** | The OpenTelemetry SDK (PydanticAI's instrumentation emits spans into it) | Stack | — | stack |

**Plain code, on purpose (each smaller than a framework):** the learning
engine and Susumu, which are the demonstrated part (ADR-010); the
budget-pool accounting (a few queries over recorded usage, on top of
PydanticAI's per-run limits); and the citation and report checks, which
are rules over IDs.

### Later (Could), recorded so they aren't re-decided

- **The text speaking partner (X3):**
  - Japanese role-play that keeps to known words plus one new word a turn,
    checked by a tokenizer in code;
  - text only, because voice recordings are sensitive and costly;
  - built only if spend is under plan at week 2.
- **A quiz as an MCP App (X4):** inside a learner's own assistant. It
  needs OAuth on Juku's MCP server; after the window.
- **The group digest (X1) and WhatsApp delivery (X2):** after the window.

## Settled with Arthur (2026-10-27: "go with your recommendations", "rush")

| # | Decision | Settled as |
|---|---|---|
| 1 | The repo name | `juku-agents`. Arthur renames the folder before anything goes to GitHub |
| 2 | The alert contact point (ADR-009) | A Telegram bot that messages only Arthur |
| 3 | Grafana or cron-only monitoring (ADR-009) | Grafana, if spike 3's idle memory fits; otherwise cron alerts |
| 4 | The gateway's per-key rate limit and actor check (ADR-012, ADR-018) | Both built in the gateway repo before launch, as gateway work |
| 5 | Time budget and launch timing | As fast as possible: about 3–4 weeks of building in parallel tracks, once the gates are cleared. Launch as soon as the launch gate passes, with the counted window starting at launch even if it spans the December exam (Phase 2, Time budget) |
