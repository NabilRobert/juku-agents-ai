# Phase 5: Architecture Decisions

Short ADRs, proposed 2026-10-27. "Settled" ones were decided with Arthur;
the rest are recommendations, open until he agrees (see the end).

### ADR-001: The users are Indonesian JLPT learners in a study group (settled)

**Decision:** adults preparing for N5–N3, recruited from a study group
Arthur joins as a member. He is studying Japanese himself, so he uses it
too, recorded separately.

**Why:**
- **Reach:** JLPT study groups are numerous and open to join, and Arthur
  has a genuine reason to be in one.
- **Weekly use:** studying is a weekly habit, with the exam as a deadline.
- **Low-risk data:** the database holds only public dictionary data;
  users' data is questions about words.
- **A database fit:** the dictionaries are relational, and every answer
  can be checked against them.
- **Cost:** short questions and answers fit $5.
- It also fits a Japanese reviewer's frame without explanation.

**Rejected:**
- *A developer community's resource directory:* public data, but a small,
  simple table and a weak reason to come back each week.
- *A workplace data assistant:* the strongest weekly use, but it needs a
  workplace and an employer's OK, and its data could never appear in
  public evidence.
- *A local business's sales data:* commercial and confidential, so the
  public evidence would be mostly redacted.

### ADR-002: Open dictionaries in Postgres, served by MCP-backbone (settled)

**Decision:**
- JMdict, KANJIDIC2, KRADFILE/RADKFILE, Tatoeba and a community JLPT list,
  loaded by committed scripts into their own database.
- MCP-backbone serves it through "connect your own database", on its own
  workspace and key, with a read-only login.

**Why:** it reuses Project 1 exactly as a stranger would use it, and every
query goes through its validator, cost check, row cap and audit log.

**Rejected:**
- *Letting the model answer from memory:* the failure this project exists
  to measure.
- *A vector store over textbooks:* copyrighted material, not
  database-backed, and the answers can't be checked against rows.
- *Scraping an online dictionary:* terms of service, and no stable
  snapshot.

### ADR-003: A web page first, WhatsApp later (settled)

**Decision:** a small web page on Arthur's domain. WhatsApp comes only
after the web page has run its window.

**Why:** no third-party approval, no phone numbers to store, full control
of consent and deletion screens.

**Rejected:**
- *WhatsApp first:* Meta business verification, a dedicated number, phone
  numbers as personal data, and per-conversation pricing.
- *Telegram:* easy, but less used than WhatsApp in Indonesia, and Arthur
  prefers WhatsApp as the second channel.

### ADR-004: A thin Python app as the MCP client

**Decision:**
- Python 3.12, FastAPI, server-rendered Jinja2 with a little TypeScript (as
  in MCP-backbone's console), SQLAlchemy and Alembic for its own records.
- The MCP Python SDK client talks to the gateway over Streamable HTTP.
- An OpenAI-compatible client talks to Sumopod. The tool loop is written
  by hand, about a hundred lines, so every call is recorded and traced.

**Path:** browser → app → gateway → MCP-backbone → dictionary database.
The Rekomendasi button takes the same path with no model.

**Why:** the tool loop is the subject being monitored, so it must be
visible, not hidden in a framework. It's the stack Arthur's other Python
projects use.

**Rejected:**
- *An agent framework (LangChain, LlamaIndex and the like):* it hides the
  loop being measured.
- *A Vue single-page app:* more front end than a thin app needs.
- *The app querying the database directly:* it would skip the stack the
  portfolio exists to show.

### ADR-005: gpt-5-mini through Sumopod

**Decision:** gpt-5-mini, with the lowest reasoning effort that keeps Q1 at
or above 90%, chosen by measurement in slice 4.

**Why:** measured on this stack. Over Pagila it scored 95.5% and 96.0%
strict, at $0.534 per 200 agent tasks, about $0.0027 a question, with a
13 s median (agent-eval-harness results).

**Rejected:**
- *gpt-5-nano as the default:* 91.0% on the same tasks, and a slower
  median (27 s). It stays a Could: a measured fallback near the budget's
  end.
- *gemini-3.5-flash:* six times the input price.

### ADR-006: Spend is capped in three layers

**Decision:**
1. **The app's budget guard (B1):** a per-user daily cap, a global daily
   cap, and a hard stop when the user pool is spent. It's checked before
   each model call, using costs from a sourced price table that errs high.
2. **The gateway:** the app's key may use only MCP-backbone's read tools.
   That limits what a call can do, not how much the model costs. A per-key
   rate limit is a Should, built in the gateway repo.
3. **The Sumopod key cap**, about $4.50: the backstop.

**Why:** the key cap alone stops abruptly, mid-answer, with an error the
user sees, and the provider counts spend after the fact. The app's guard
stops cleanly and says why.

**Rejected:**
- *Relying on the key cap alone:* see above.
- *Prepaid credits per user:* more app than this needs.

### ADR-007: Invite codes and nicknames, no email

**Decision:**
- Arthur issues one random code per person.
- The user picks a nickname; the app stores only the code's hash.
- A lost code is replaced by a new one.

**Why:** the least personal data that still bounds access and cost.

**Rejected:**
- *Google sign-in:* stores an email address, and needs OAuth setup.
- *Email magic links:* stores email, and needs a mail sender.
- *Open sign-up:* unbounded cost and abuse.

### ADR-008: Monitoring is Grafana over Postgres, with alerts

**Decision:**
- **Records:**
  - the app writes a per-call record for every MCP tool call (M1);
  - the gateway's audit log is imported after its hash chain is verified
    (M2);
  - MCP-backbone's audit log is read through a read-only role (M3).

  All of these land in a `monitoring` schema in the app's Postgres.
- **Dashboard and alerts:** one Grafana OSS container, with a Postgres data
  source on a read-only role. Dashboards and alert rules are provisioned
  from committed files. It is loopback only and behind Arthur's login,
  with a 256 MB memory cap.
- **Heartbeat:** the app writes a row every minute, and an alert fires when
  it's stale. That's the dead-man's switch.
- **Alerts go to Arthur only.** The contact point (a Telegram bot that
  messages only him, or email) is his choice.
- **Traces:** to Project 6's Jaeger, content off, with the same trace ID in
  the per-call record, so a dashboard row leads to its trace.

**Why:**
- Project 6 deliberately stops at traces: metrics, dashboards and alerting
  are non-goals there. The tools' health is this project's subject, so it
  lives here.
- Grafana reading Postgres directly is one service and no metrics pipeline.
  The numbers on the dashboard come from the same tables as the committed
  evidence SQL.

**Rejected:**
- *Prometheus + Grafana:* two services, and a metrics endpoint to add to
  every project, on a small shared server.
- *Jaeger's span metrics (its Monitor tab):* it needs Prometheus too.
  Project 6 lists it as future work.
- *A hosted uptime or monitoring service:* another account, and data
  leaving the server.
- *Cron scripts only:* alerts but no dashboard. It is the fallback if
  Grafana's measured memory doesn't fit.

### ADR-009: The recommender is a deterministic SQL ranking

**Decision:**
- **Precomputed tables** (built by the load scripts, read-only at run
  time):
  - `word_kanji(entry_id, kanji)`;
  - `word_level(entry_id, level, tier, nf_rank)`. `tier` is 1 for
    JMdict's priority-tagged common words and 2 otherwise; `nf_rank` is
    the frequency band;
  - `kanji_leverage(kanji, level, common_words)`: how many tier-1 words at
    or below that level contain the kanji.
- **Inputs:** the target level `L` and the known entry IDs `K` (integers,
  capped at 500, validated by the app).
- **Known kanji:** every kanji of the easier levels, plus the kanji of the
  words in `K`.
- **Candidates:** words at level `L` or easier, not in `K`, with at most
  one unknown kanji. Kana-only words qualify.
- **Ordering:** lexicographic, with no tuned weights, so each position can
  be explained:
  1. tier (common words first);
  2. gaps first (words from easier levels before words at `L`);
  3. the leverage of the word's unknown kanji (higher first; words with
     no unknown kanji count as 0);
  4. `nf_rank`;
  5. `entry_id`, for determinism.
- **Variety:** at most 3 of the 10 suggestions share the same new kanji
  (a `row_number()` window).
- **Reason:** built from the row, for example "1 kanji baru: 日, muncul di
  34 kata umum N5".
- **Frozen during the window.** The ordering may be tuned once before
  launch against Arthur's judgement, then frozen, so uptake (R2) is
  comparable. Any later change is a "what changed", with before and after.

**Why:**
- It's explainable, testable to the exact row (Phase 1, R1), and costs no
  model call.
- It exercises the same MCP tools and limits as chat, so monitoring can
  compare the two paths.
- The candidate set is the JLPT-listed words, a few thousand rows, so the
  cost check should pass easily. *Spike 2 confirms it.*

**Rejected:**
- *Asking the model for suggestions:* not checkable, costs money, varies
  run to run.
- *Collaborative filtering ("learners like you"):* needs far more users
  than this will have, and it builds profiles of people.
- *Spaced repetition:* a scheduler, not a recommender, and a large feature
  (a Phase 1 non-goal).
- *A dedicated recommender MCP tool now:* MCP-backbone allows only built-in
  SQL functions, so a custom function isn't possible there, and a second
  server is more to run. It stays a Could: a measured comparison of
  generic SQL against a purpose-built tool.

**Known risk:** community JLPT lists name words by spelling, and some
spellings match several JMdict entries. The mapping rules and the
unresolved count are reported in slice 1, not hidden.

### ADR-010: Quality is measured offline first, then in a closed loop

**Decision:**
- **Offline:** a new agent-eval-harness task set of about 40 tasks,
  written in Indonesian. Their gold answers are computed by SQL from the
  same snapshot, so they're checkable. It also has one recommender task
  with fixture learners. Strict scoring, pass^k reported. Gate: Q1 ≥ 90%
  before launch.
- **Online:** every answer's citation check (Q2), Arthur's weekly
  hand-graded sample of 20 against a rubric committed before launch (Q3),
  and user ratings (Q4).
- **The loop:** weekly, any failure category seen 3 or more times becomes
  a new task, then a fix, then a rerun. The new task is **paraphrased**: a
  user's words go into a task only with that message's quote permission.
- **Evidence:** committed SQL over the records, as in Pitstop.

**Rejected:**
- *A model as judge for every answer:* it costs budget, and a judge's
  verdict is one more unverified claim. It's used nowhere in the headline
  numbers.
- *Ratings alone:* too few and too biased to stand by themselves.

### ADR-011: Hosting is Docker Compose on the shared server

**Decision:**

| Container | Contents | Memory cap |
|---|---|---|
| `app` | FastAPI app, non-root, read-only filesystem, `cap_drop: ALL` | 256 MB |
| `db` | `postgres:16` with two databases: `app` (records and `monitoring`) and `dict` (the dictionary). MCP-backbone's login may connect only to `dict`, read-only | 384 MB |
| `grafana` | Grafana OSS, provisioned from files | 256 MB |

- Only `app` and `grafana` are reached, through the server's existing
  proxy. `db` publishes no public port.
- The gateway and MCP-backbone run as they already do. Deploying the
  gateway in front of MCP-backbone for this app is a server step done by
  Arthur or the server session.

**Why:** isolated from the other projects' data, capped, and the same
pattern as the Pitstop demo.

**Rejected:**
- *Separate Postgres containers for app and dictionary:* about 100 MB
  more for isolation that roles already give.
- *The dictionary in MCP-backbone's own Postgres:* it would share a
  cluster with MCP-backbone's key data.

### ADR-012: A fixed window, and results reported as they are (settled)

**Decision:** the measurement window is the first 4 weeks after launch,
with the metrics, floors and rubric committed before launch. If adoption
misses the floors, the case study says so and what was learnt. The window
isn't stretched, and Arthur isn't counted.

**Why:** the point of this project is credible real-use numbers. Moving
the goalposts afterwards would undo that.

## Open for Arthur

| # | Decision | Recommendation |
|---|---|---|
| 1 | The product and repo names | See the report |
| 2 | Alert contact point (ADR-008) | A Telegram bot that messages only you |
| 3 | Grafana vs. cron-only monitoring (ADR-008) | Grafana, if spike 3's idle memory fits |
| 4 | The gateway's per-key rate limit (ADR-006) | Build it in the gateway repo before launch |
| 5 | Launch timing against the December JLPT | Don't rush for December. If it's ready after about 20 November, run December as an uncounted soft launch and start the counted window in early January, towards the July 2027 exam |
