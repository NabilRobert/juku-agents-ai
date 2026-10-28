# Phase 2: Requirements & Constraints

Phases 3 and 4 are folded into this doc and Phase 5, as in Pitstop. The
build goes in slices ([slice plan](slice-plan.md)).

## Core scenario

1. **Joining.** A learner in the study group gets a personal invite code
   from Arthur. They open Juku and read a one-screen consent notice in
   Indonesian. They confirm they're 18 or older, then pick a nickname,
   their target level (N5–N2) and, optionally, their exam date.
2. **Studying** during the week (no model call, $0):
   - **Rekomendasi:** 10 words to learn next, each with its reason.
   - **Kuis:** a short quiz on meanings and readings, generated and graded
     in code. Wrong answers go to the mistakes queue.
   - **Bacaan:** example sentences where they know every word but one.
   - **Rencana:** their coverage of the level, and the pace they need for
     the exam date.
3. **Asking.** They ask the chat, in Indonesian: "kenapa saya selalu salah
   baca 生?", "apa bedanya 見る dan 観る?". The chat agent looks up their
   progress through Juku's MCP server and the dictionary through
   MCP-backbone, then answers with citations. The app checks each
   citation against the rows returned.
4. **The weekly report.** Each Sunday evening, a scheduled pipeline runs
   for every learner who was active that week:
   1. SQL computes the facts;
   2. the planner picks next week's focus;
   3. the writer drafts the report;
   4. the critic reviews both;
   5. code approves.

   The learner opens it as "Laporan minggu ini".
5. **Feedback.** They rate outputs with a thumbs up or down.
6. **Arthur's view.** He watches tool and pipeline health on a private
   dashboard, gets alerts, and each week turns failures into eval tasks.
7. **Leaving.** At any time, "Hapus data saya" removes everything about the
   learner.

## Requirements

**The learning engine (deterministic, $0)**
- **LE1. Progress.**
  - A word is *known* when the learner marks it so, or answers its quiz
    item correctly on two separate days.
  - *Coverage* is the share of a level's listed words and kanji that are
    known.
  - All of it is computed in SQL, never by a model.
- **LE2. Quizzes.**
  - Multiple choice on meaning or reading.
  - Distractors are drawn from the same level and similar items, such as
    shared kanji or a similar reading.
  - Generated and graded in code.
- **LE3. Recommender:** i+1 with kanji leverage (Phase 5, ADR-010), with
  a stated reason for each word.
- **LE4. Reading practice (Should):** OpenJLPT's example sentences (from
  Tatoeba, with furigana), tokenized with SudachiPy and matched to word
  IDs, in which every word but one is known. Coverage is measured in
  spike 4.
- **LE5. Pace planner (Should):** from the exam date and the current
  coverage, the words a week needed to reach a target coverage. The
  formula is committed and shown to the learner.
- **LE6. Mistakes queue (Should):** wrong answers enter Leitner boxes
  1–5. An item moves up a box when it is answered right and goes back to
  box 1 when it is answered wrong, with fixed intervals per box.
- **LE7. Fixtures:** each of LE1–LE6 is pinned by committed fixture
  learners with exact expected outputs (Phase 1, E1). The tests are
  mutation-checked.

**Juku's MCP server (the learner's data)**
- **SM1.** A small MCP server in this repo exposing **read-only**,
  learner-scoped tools: `get_progress`, `get_mistakes`, `recommend_words`,
  `find_reading_sentences`, `get_plan`, `get_recent_activity`,
  `get_memory`.
- **SM2. Identity comes from the session, never from arguments.**
  - The app mints a short-lived, signed token for one learner and one
    purpose (chat, or one pipeline run), and opens the MCP session with
    it.
  - No tool takes a learner ID.
  - A test shows that no call can return another learner's rows
    (Phase 1, M7).
- **SM3.** Its database login can read the progress tables and the
  dictionary, nothing else, and write nothing.
- **SM4.** **No agent tool writes learner data.**
  - When the chat suggests marking a word known, it shows a button; the
    learner's click writes, through the app. That is approval decided in
    code, as in Pitstop.
  - There is one action tool, `request_replan`. It lets Shiori ask Keiko
    for a new plan from chat. It only queues a Keiko run (at most 1 a day
    per learner), whose result passes Tadashi and code like any plan. The
    learner then accepts or ignores it.
- **SM5.** It sits behind the gateway like MCP-backbone, with its own audit
  log, and spans that follow Project 6's conventions.

**Agent identity and delegated authorization**

There's no settled standard yet for "who is this agent, and what may it
do for whom", and multi-hop delegation is the open part. Juku implements
a small, testable version of it, and reads the MCP authorization spec
current at build time before fixing the details. Arthur notes that a July
2026 revision tightened authorization; spike 6 reads it.

- **ID-R1. Each agent is its own identity.** Shiori, Keiko, Nikki and
  Tadashi each have their own gateway key and allow-list. No key is
  shared, and the app's own key can't call tools.
- **ID-R2. Every call carries a delegation chain.**
  - It is a short-lived token, signed by the app, with these claims:
    - the learner, as a pseudonymous ID (the subject);
    - the chain of actors, nested as in OAuth 2.0 Token Exchange's `act`
      claim (RFC 8693);
    - the purpose (chat, or a weekly run, with its run ID);
    - the allowed tools;
    - the audience (the Juku MCP server);
    - the expiry.
  - It travels in the MCP request's `_meta`, which the gateway passes
    through unchanged (spike 6 checks this).
  - It is never the gateway's own credential: no token passthrough.
- **ID-R3. Delegation only narrows.** In the one multi-hop path, learner →
  Shiori → Keiko → Juku MCP server, the token Keiko gets has:
  - a subset of Shiori's tools;
  - an expiry no later than Shiori's;
  - the same learner;
  - a chain one hop longer.

  More than 2 agent hops is refused.
- **ID-R4. Verified at both ends.** The Juku MCP server checks the
  signature, audience, expiry, scope and chain. The gateway checks
  (Should) that the last actor in the chain is the agent whose key made
  the call.
- **ID-R5. Every hop is logged**, with the chain, in the audit log and
  the per-call records (Phase 1, ID1–ID2).
- **ID-R6. The learner can see who accessed their data.** A "Siapa yang
  mengakses datamu" page lists which agent read which kind of data, and
  when: tool names and times, never content.

**Guardrails (enforced in code, as usual)**

Every guardrail lives in a committed rule file (or the gateway's policy
file) and is enforced in code, not described in a document. Each has a
test that fails when the rule is removed (Phase 1, G1).

| Guardrail | Enforced in | Test |
|---|---|---|
| Spend: reports pool, chat pool, per-learner and global daily caps, hard stop | The app's budget guard (B1), checked before every model call | Each cap is reached in a test, and the call is refused |
| Spend backstop | The Sumopod key cap | Checked once at key creation, and recorded |
| Tools per agent | The gateway's policy (deny by default) | Each agent calling a tool outside its list is refused |
| Data scope: one learner per session | The Juku MCP server (SM2, ID-R2) | The cross-learner suite (M7) |
| Delegation: narrowing only, depth ≤ 2, expiry, audience | The Juku MCP server, and the gateway's actor check | The delegation suite (ID2) |
| No writes by agents, except `request_replan` | The tool list, and the server's read-only login | A write attempt is refused at the tool and at the database |
| Dictionary is read-only | MCP-backbone's validator, and a read-only transaction and login | MCP-backbone's red-team suite, plus a Juku-specific check |
| Injection in tool outputs | The gateway's detector (fails closed) | The attack suite (SAF1) |
| Report claims: numbers, words, levels, citations, staleness | Code checks after Tadashi (AG1) | Planted bad reports are blocked |
| Memory: evidence required, learning-only categories | Code (MEM-R2, MEM-R3) | Notes without evidence, or in a forbidden category, are refused |
| Privacy of public evidence | The privacy check (EV2) | A planted nickname or small cell fails the check |
| 18+ and consent before first use | The app | No activity is possible without a consent record |

**Humans in the loop**

| Decision | Who decides | Never automatic |
|---|---|---|
| Whether a word is "known" | The learner (a click), or two correct quiz answers on separate days (a code rule) | An agent saying so |
| Whether a memory note stays | The learner can remove it, or mark it wrong, at any time | |
| Whether a new plan from `request_replan` is used | The learner | |
| Whether a report goes out | Code, after Tadashi; otherwise the facts-only fallback | The model approving itself |
| Whether a prompt or rule changes | Arthur, from the feedback job's drafts (AG4) | Any self-modifying prompt |
| Whether a failure becomes an eval task, and its fix | Arthur, in the weekly review | |
| Launch, and every paid eval run | Arthur | |

**Safety evaluation**
- **SAF-R1.** An attack suite of about 15 tasks on Juku's own surfaces:
  - injection planted in a **fixture copy** of the Tatoeba sentences
    (never in the live data);
  - attempts to reach another learner's data;
  - attempts to plant a false or forbidden memory note through chat;
  - attempts to widen a delegation;
  - attempts to make an agent call a tool outside its list.

  Which attacks should succeed is predicted and committed before the run,
  as in the gateway project.
- **SAF-R2.** Run with the scripted "gullible" agent, with and without the
  gateway ($0), then once with the real model (paid, with Arthur's OK).

**Memory (inspectable, evidence-backed)**
- **MEM-R1. Three kinds, all in Postgres:**
  - **what the learner knows** (known words, coverage, mistakes), always
    recomputed from the activity, never written by a model;
  - **what happened** (the activity rows: quiz answers, sessions, chat
    topics, reports opened);
  - **agent notes**: short statements about how the learner learns.
- **MEM-R2. Notes are proposed, never written, by agents.**
  - An agent returns proposed notes in its structured output, each with
    a category and the IDs of the activity rows that support it.
  - Code stores a note only if its category is on the allowed list and
    its evidence exists, belongs to this learner and actually shows the
    pattern (for example, ≥ 3 misses of the same type).
  - Rejected proposals are counted (Phase 1, MEM2).
- **MEM-R3. Allowed note categories are about learning only:**
  - recurring confusions;
  - preferred kinds of example;
  - pace;
  - levels or topics avoided.

  Anything about health, emotions, personal life, work or other people is
  refused in code, and the critic treats it as high severity.
- **MEM-R4. Consolidation.** Each weekly run:
  - recomputes what is known;
  - lets a note lapse once its evidence is more than 30 days old and
    hasn't recurred;
  - records why each note was kept or dropped.
- **MEM-R5. The "Shiori ingat…" page** lists every memory item with its
  evidence and age. A learner can:
  - remove a note, which also stops the same note being proposed again
    for 30 days;
  - mark it wrong, which counts towards MEM3;
  - unmark a known word.
- **MEM-R6.** Agents read memory only through `get_memory` and the other
  scoped tools on Juku's MCP server.

**Agents**

| Agent | Role | Tools through the gateway |
|---|---|---|
| **Shiori** (chat) | Answers on demand, in Indonesian, with citations | MCP-backbone read tools (dictionary); Juku's server, scoped to this learner |
| **Keiko** (planner) | Picks next week's focus (words, kanji and mistakes to review) **only from candidates the engine computed**, says why, and may propose notes (MEM-R2) | Juku's server, scoped to this learner and run |
| **Nikki** (writer) | Writes the weekly report (≤ 300 words, Indonesian) from the facts and Keiko's plan | none: works only from what it is given |
| **Tadashi** (critic) | Reviews Keiko's and Nikki's outputs against the facts they were given, listing issues with a severity | none |

- **AG1. The pipeline** runs per learner: facts → Keiko → Tadashi → Nikki → Tadashi.
  - An output passes only if Tadashi reports no high-severity issue. High
    severity means any of:
    - a number not in the facts;
    - a word that isn't among the candidates, or not at the stated level;
    - a missing citation;
    - a claim contradicted by newer activity (stale memory, Phase 1,
      MEM4);
    - a note outside the allowed categories.
  - At most 2 revisions per output.
  - **Code checks the high-severity rules itself as well**, so a missed
    issue can't pass.
  - If an output still fails, the learner gets a facts-only report built
    from a template, and the fallback is counted (Phase 1, P3).
- **AG2. Scheduling** by external cron (as in Pitstop), Sunday 18:00 **in
  each learner's own timezone** (WIB by default). Indonesia has three
  timezones, and some learners live in Japan.
  - Runs are idempotent jobs keyed by (learner, week): a rerun never
    duplicates a report (fitness function FF7).
  - Each run records its start and end.
  - A dead-man's switch alerts if a due run hasn't completed within an
    hour.
- **AG3. Run records:** `pipeline_runs`, `agent_outputs` and
  `critic_reviews`, plus a Run Inspector page for Arthur only. It shows
  each run's facts, every model call, each review and the decision.
- **AG4. Feedback job (Should).** Weekly, it reads recurring patterns in
  Tadashi's issues and drafts prompt changes for Arthur. **Nothing is ever
  applied automatically.**
- **AG5. Chat:**
  - Answers state facts only from tool results, with citations in a fixed
    format.
  - The app checks every cited ID against the rows returned in that turn,
    and labels an answer that fails "unverified" (Phase 1, Q2).
  - When the data doesn't have it, the answer says "tidak ada di data".
  - Answers stream to the page as they're written (server-sent events), so
    a 15 s answer doesn't look stuck (Should).
- **AG6. A learner in distress.**
  - A moderation check runs on each message before the model sees it:
    the provider's moderation endpoint if Sumopod exposes it, otherwise a
    small local classifier.
  - If a message suggests self-harm, Shiori gives a fixed, kind reply with
    Indonesia's official mental-health line (verify the number at build
    time). No improvised answer.
  - Arthur gets an alert with no content in it.

**The interface (thin on purpose)**
- **UI1.** Server-rendered pages, in Indonesian: Chat, Kuis, Rekomendasi,
  Bacaan, Rencana, Laporan, **Shiori ingat…** (memory), and Settings
  (level, exam date, timezone, download my data, delete my data).
- **UI2.** The browser holds no model or MCP key. The app reaches data only
  through the gateway, except its own writes from learner clicks.
- **UI3.** A thumbs up or down on chat answers and reports, with an
  optional reason chosen from a list.

**Frontend performance (lazy loading and a performance budget)**

Learners use mid-range Android phones on mobile data, so the frontend is
built to a budget and checked in CI (ADR-024).
- **FE1. Server-rendered HTML first.** Pages arrive ready to read. **Vue 3
  islands** (Arthur's stack) mount only where a page is interactive: chat,
  quiz answers, ratings, "mark known", loading more history. There's no
  client router and no single-page app (Phase 5, ADR-024).
- **FE2. Load only what a page needs.** Vite builds one small bundle per
  page, so the chat's streaming code loads only on Chat. Heavy pieces
  load on demand with dynamic `import()`. Everything below the fold is
  lazy: images use `loading="lazy"`, and long lists (chat history,
  "Shiori ingat…", reports) load 20 at a time.
- **FE3. Japanese fonts without the megabytes.** Japanese text uses the
  system font stack (Hiragino, Noto Sans CJK, Yu Gothic, Meiryo), so no
  multi-megabyte web font is downloaded. If a web font is ever needed, it
  is Noto Sans JP from Google Fonts, which is split into unicode-range
  slices, with `font-display: swap`.
- **FE4. Readings as real markup.** Furigana uses `<ruby>`, so it is
  accessible and needs no script.
- **FE5. Fast delivery.** zstd and gzip compression, and HTTP/2 and 3, from
  Caddy. Hashed asset names with a one-year immutable cache. Tailwind
  CSS, with unused classes stripped at build. Icons in one inline SVG
  sprite.
- **FE6. Nothing waits on the model unless it has to.**
  - Reports are pre-written.
  - Quizzes come 10 items at a time, with the next batch prefetched.
  - The $0 pages never call a model.
  - Chat streams (AG5).
- **FE7. The budget (CI fails over it):**
  - ≤ 100 KB of JavaScript per page and ≤ 30 KB of CSS, compressed;
  - LCP ≤ 2.5 s, INP ≤ 200 ms and CLS ≤ 0.1 on Lighthouse's mobile
    profile.

  Checked by Lighthouse CI on every commit (fitness function FF12).
- **FE8. Real-user measurement, privately.** The `web-vitals` library
  reports LCP, INP and CLS to the app's own endpoint: page type and value
  only, no learner ID or content. The p75 values go on a Grafana panel.
- **FE9 (Could): offline quizzes.** A service worker (Workbox) caches the
  shell and the next quiz batch for patchy connections.

**Japanese input**
- **JI1.** Input is normalised before lookup: full- and half-width forms,
  romaji to kana, and kana variants (jaconv). Words are tokenized and
  given normalised forms with SudachiPy.
- **JI2.** Fuzzy search, so "taberu", "食べる" and a near-miss typo find the
  same word. It's a Juku MCP tool (`search_words`) that calls OpenJLPT's
  own Python package (ranked search over kanji, kana, romaji and
  English). It's reused rather than built, and it lives in Juku's server
  because MCP-backbone's validator allows only built-in SQL functions.

**Dictionary data**
- **D1.** Its own Postgres database, loaded by a committed script from a
  pinned **OpenJLPT** release (Phase 5, ADR-003). It holds 7,811 words
  linked to JMdict, 2,383 kanji with readings, radicals, strokes and
  frequency, 526 grammar points, and Tatoeba example sentences with
  furigana. The download isn't committed; its version and checksum are.
  - **Updates:** OpenJLPT's IDs are stable across releases, so a learner's
    known words survive an upgrade. The upgrade script still reports any
    ID that disappeared.
  - **Grammar:** grammar questions are answered from OpenJLPT's grammar
    points, with citations, like words and kanji.
  - **A full JMdict import, for words outside the JLPT lists, is a Could.**
- **D2.** Licences attributed on an "about the data" page before launch:
  - OpenJLPT is CC BY-SA 4.0 and built on JMdict and KANJIDIC2 (EDRDG),
    Jonathan Waller's JLPT lists and Tatoeba. The wording follows its
    NOTICE.md;
  - any dataset Juku derives and redistributes is CC BY-SA 4.0 too;
  - the official JLPT has published no word lists since 2010, so the
    levels are community estimates, and the page says so.
- **D2b. Arthur's textbook PDFs are a private coverage checklist only.**
  They're used to spot topics or words OpenJLPT lacks. They're never
  committed, never sent to a model, and never a source of copied text.
- **D3.** MCP-backbone serves it through "connect your own database", with
  a read-only login, on its own workspace and key.
- **D4.** Schema comments and read-only views that make it easier for a
  model to use. They are versioned, because changing them is a tool-level
  change (Phase 1, F2).

**Monitoring (core)**
- **M1.** The app writes a per-call record for every MCP tool call: agent,
  tool, server, duration, outcome, error category, row count and trace ID.
  No arguments, SQL or results.
- **M2.** The gateway's audit log is imported on a schedule. The hash chain
  is verified first, and a broken chain is an alert.
- **M3.** MCP-backbone's audit log for this workspace is read through a
  read-only role, for refusal reasons by layer.
- **M4.** A private dashboard over M1–M3, the run records and the app's
  records:
  - calls, errors and latency per tool and per agent;
  - refusals by layer;
  - tool calls per output;
  - recovery after a failed query;
  - the pipeline's runs, approvals, revisions and fallbacks;
  - budget used;
  - activity per day.

  Provisioned from committed files. **No panel ever shows a nickname,
  question text or one learner's data**, so a screenshot is safe by
  construction.
- **M5.** Alerts go to Arthur only, and each one is tested on purpose
  before launch:
  - the app's heartbeat is stale for more than 5 minutes;
  - a scheduled run is missed;
  - the budget reaches 50%, 80% or 100%;
  - a tool's error rate exceeds 5% in an hour;
  - the injection detector flags anything;
  - the audit chain is broken;
  - a cross-learner access attempt is refused.
- **M6.** Every request and every pipeline run is one trace, sent to
  Project 6's viewer, with content off by default.

**Spend control**
- **B1. Budget guard**, checked before every model call, with two separate
  pools (see the [cost model](slice-plan.md#cost-model)):
  - **reports** have their own reserved pool, so chat can't starve them;
  - **chat** has a per-learner cap of 20 questions a day, a global cap of
    $0.20 a day, and a hard stop when its pool is spent.

  When chat stops, the learner is told plainly, and the $0 features keep
  working.
- **B2.** Cost is computed from recorded token counts and a committed,
  sourced price table (the harness's `prices.yaml` convention). It errs
  high.
- **B3.** The Sumopod key cap (about $4.50) is the last line, not the
  first.

**Evidence and docs**
- **EV1.** Every published number comes from a committed SQL file, with its
  output committed (as in Pitstop).
- **EV2.** A privacy check before anything is published: no nicknames,
  codes, question or report text, timestamps finer than a day, or groups
  under 5 learners.
- **EV3.** The case study, a JOURNEY log and a portfolio entry in EN, JA
  and ID (handed to the site session; this repo doesn't edit the site).

**Later features (Could)**
- **X1. Group digest.**
  - A weekly, anonymised summary for the study group, such as "the group
    learnt 340 words this week; the most-missed kanji was 曜".
  - Computed in SQL from learners who opted in, and shown only when there
    are 5 or more of them.
  - $0.
- **X2. WhatsApp delivery** of the weekly report, after the web page has
  run its window. It needs Meta business verification, and phone numbers
  are personal data: they'd be hashed, under their own consent.
- **X3. Text speaking partner.**
  - A short role-play conversation in Japanese that keeps to words the
    learner knows, plus at most one new word a turn.
  - Code checks each reply with a Japanese tokenizer and flags words
    outside that set.
  - Limited to 1 conversation of 10 turns a day per learner, from the chat
    pool, and only if spend is under plan at week 2.
- **X4. A quiz as an MCP App.** Juku's quiz, offered as an interactive
  MCP App, so a learner can take it inside their own Claude or ChatGPT.
  It needs OAuth on Juku's MCP server and its own consent wording.
  Considered only after the window.

## Privacy

The data is low-risk (what someone knows of Japanese), but it belongs to
real people, so it gets the care Phase 1 promises. The frame is
Indonesia's Personal Data Protection Law (UU PDP, Law 27/2022): consent
for a stated purpose, access, deletion and withdrawal. This is design
care, not legal advice.

**Consent**
- A one-screen notice in plain Indonesian before first use, with a
  separate tick for each of:
  1. using the service, including progress tracking, weekly reports and
     Shiori remembering how they learn (agent notes they can see and
     remove);
  2. anonymous aggregate numbers appearing in Arthur's public portfolio;
  3. (optional, off by default) being counted in the group digest (X1);
  4. (optional, per message) letting a specific output be quoted, chosen
     when rating.
- **Processing abroad, stated plainly.** Questions and report facts are
  sent to an AI model provider outside Indonesia. UU PDP has rules on
  transfers abroad, so the notice says so, and the "about" page names the
  provider.
- **18+ only.** Many JLPT learners are school students, and under UU PDP a
  child's data needs a parent's consent. Requiring 18+ keeps it simple.
- Withdrawal is "Hapus data saya", at any time.
- The consent text and its version are committed. Each learner's record
  keeps the version they accepted and when.

**What is stored**

| Stored | Why | Not stored |
|---|---|---|
| Nickname (the notice suggests not using a real name) | Shown in the page | Real name, email, phone number |
| Hash of the invite code | Login | The code itself |
| Target level and exam date (optional) | Plan and coverage | |
| Known words; quiz answers and results; the mistakes queue; sentences read | The learning engine | Free-text notes |
| Chat questions and answers; weekly reports | History; Arthur's weekly review | |
| Agent notes (learning-only categories, each with its evidence) | Memory that the learner can see and remove | Notes about health, emotions, personal life, work or other people (refused in code) |
| Run records (facts given to agents, their outputs, critic reviews) | The Run Inspector, for Arthur only | Anything about another learner in a learner's run |
| Ratings, reasons, quote permissions | Quality metrics | |
| Timestamps, token counts, cost, per-call records, trace IDs | Metrics, budget, monitoring | Tool arguments or results in traces (content off) |
| | | Voice of any kind |
| | | IP addresses: the site's access log is set not to keep them, or to keep them for 7 days at most (decided at deploy) |

**Who sees it:** the learner sees their own; Arthur sees it for operating
and reviewing. Agents see only one learner's data in a session, enforced
by SM2.

**Retention**
- Chat text, reports and run-record content: deleted 60 days after the
  measurement window closes. After that, only anonymised aggregates
  remain.
- Learning-engine data: kept while the learner keeps using Juku; deleted
  after 90 days of inactivity, with notice on the page beforehand.
- Per-call records and metrics: kept without text; the learner ID is
  removed at the 60-day point.
- Traces: Project 6's retention period, with no content and only a
  pseudonymous learner hash.
- Backups: rolling 7 days, encrypted, so deleted data leaves them within 7
  days.

**Deletion**
- "Hapus data saya" deletes the learner's rows immediately, cascading over
  progress, quizzes, chat, reports and run-record content. It tells them
  about the 7-day backup tail.
- Their per-call records stay, with the learner ID removed, so totals still
  add up.
- Arthur can do the same on request for someone who has lost their code.

**Access**
- "Unduh data saya" exports everything Juku holds about the learner as a
  JSON file: the right of access, not only deletion.

**Public evidence**
- Aggregates only, never below 5 learners in any cell; dates by week.
- An output is quoted only with that message's quote permission, and
  without the nickname.
- Dashboard screenshots are safe by construction (M4), and are still
  checked by eye.
- The privacy check (EV2) runs before every publish.

## Non-functional

- **Scale: built for ten, designed for thousands.** The data design
  applies from day one, and the growth path uses existing tools
  ([scale path](scale-path.md)):
  - a narrow, append-only event table, partitioned by month;
  - incrementally updated summaries;
  - text kept apart from metrics;
  - `cohort_id` and timezones from the start;
  - stateless services.
- **Anti-regression:** fitness functions in CI (FF1–FF11 in the scale path)
  fail the build when a change degrades query plans, cost per output,
  tool schemas, idempotency, guardrails or privacy. The harness's
  regression gate covers agent quality.
- **Footprint:** a small shared server, so every container has a memory
  cap. Grafana's idle memory and the MCP server's are measured and
  published.
- **Latency:** chat p50 ≤ 15 s and p95 ≤ 40 s; the $0 pages under 1 s,
  within the frontend budget (FE7).
  Reports are written ahead of time, so they load at once.
- **Availability:** best effort, but every outage and missed run is noticed
  (M5) and counted.
- **Security:**
  - each agent has its own gateway key and allow-list;
  - no agent tool writes learner data (one action tool, `request_replan`,
    only queues a run);
  - a new key for every secret, with nothing reused;
  - invite codes are random and single-person.
- **A reviewer gets it in about 15 minutes** from the README and the case
  study.

## Constraints

- **Budget:** $5 in total, a key cap of about $4.50. Not topped up until
  building starts. No paid model calls before then. Eval runs and the
  launch each need Arthur's OK.
- **Gates before building:** the open server-security follow-ups are
  cleared (key rotations, key-only SSH on the second server), and the
  gateway is pushed. Nothing is planned to start sooner.
- **The gateway has no per-key rate limit yet.** It's listed under the
  gateway's "Next". Until it exists, rate limits live in the app (B1), and
  the gateway does auth, allow-lists, detection and audit.
- **Depends on Project 6** for the trace viewer. If it isn't deployed by
  launch, traces wait, and alerts rely on the app's own records.
- **Server work goes through Arthur** or the server's own session. No server
  details in public writing.
- **Outreach is Arthur's:** joining the group, posting, sending codes.
  Drafts are prepared for him.
- **Timing:** the December 2026 JLPT (confirm the date on jlpt.jp) drives
  study. Arthur's call is to rush: launch as soon as the launch gate
  passes. The counted window starts at launch, even if it spans the exam,
  and the write-up marks the exam date on every weekly chart, so a
  post-exam dip is read for what it is.

## Must / Should / Could

| | Item |
|---|---|
| **Must** | LE1–LE3, LE7: progress, quizzes, the recommender, with fixtures |
| **Must** | SM1–SM5: Juku's MCP server, scoped by session, read-only, behind the gateway |
| **Must** | MEM-R1–R6: structured memory, evidence-checked notes, learning-only categories, consolidation, the "Shiori ingat…" page |
| **Must** | ID-R1–R3, ID-R5: per-agent identities, delegation chains that only narrow, logging; ID-R4 at the Juku MCP server |
| **Must** | The guardrails table, each guardrail with its test; the humans-in-the-loop map |
| **Must** | SAF-R1 and SAF-R2 with the scripted agent; evaluation-driven order (each agent's tasks committed before its code) |
| **Must** | The data design in the scale path (events, summaries, separate text, `cohort_id`, timezones); fitness functions FF1–FF9 and FF11 in CI |
| **Must** | AG6 (a learner in distress); JI1 (input normalization); the dictionary update policy; "Unduh data saya"; the processing-abroad wording |
| **Must** | FE1–FE7: server-rendered pages with Vue islands, per-page bundles and lazy loading, system Japanese fonts, `<ruby>`, compression and caching, the performance budget in CI |
| **Must** | AG1–AG3, AG5: the weekly pipeline with critic and code approval, scheduling with a dead-man's switch, run records, the cited chat |
| **Must** | UI1–UI3; D1–D3; M1, M4–M6; B1–B3 |
| **Must** | Privacy as above: consent, 18+, stored/not stored, retention, self-serve deletion, public-evidence check |
| **Must** | Before launch: the offline chat task set (~40 tasks) at Q1 ≥ 90%; about 15 memory tasks at MEM1 ≥ 90%; pipeline fixtures for 10 learners |
| **Must** | EV1, EV2 |
| **Should** | LE4: reading practice (i+1 sentences) |
| **Should** | LE5, LE6: the pace planner and the mistakes queue |
| **Should** | AG4: the feedback job; M2, M3: the audit imports; D4: views and schema comments |
| **Should** | EV3: case study, JOURNEY, portfolio entry |
| **Should** | The gateway's per-key rate limit and its actor check (ID-R4), built in the gateway repo; Arthur's call |
| **Should** | ID-R6: the "Siapa yang mengakses datamu" page; SAF-R2 once with the real model |
| **Should** | FE8 (real-user web vitals); JI2 (fuzzy search); streamed answers; FF10 and the load test (Locust, 5,000 synthetic learners, $0); self-hosted error tracking (GlitchTip) |
| **Could** | X1: the group digest; X2: WhatsApp delivery; X3: the text speaking partner |
| **Could** | X4: a Juku quiz as an MCP App, so a learner can use it inside their own assistant. It needs OAuth on Juku's MCP server, and its own consent wording |
| **Could** | FE9: offline quizzes with a service worker |
| **Could** | gpt-5-nano as a cheaper fallback near a pool's end, measured as a "what changed" |
| **Won't** | Voice, open sign-up, full spaced repetition, free-writing grading, copyrighted material, a mobile app |

## Time budget: as fast as possible (Arthur, 2026-10-27)

About **3–4 weeks of building** once the gates are cleared, then the
4-week window. It's compressed by:
1. **Running independent tracks in parallel** (separate Claude Code
   sessions, one set of files each);
2. **Using existing tools** rather than building our own (scale path);
3. **Dogfooding with pipeline runs triggered on demand** instead of
   waiting for two Sundays;
4. **Building the Should items behind flags during the window**, with each
   switch-on date recorded.

| Week | Work |
|---|---|
| 0 (2 days) | Spikes 1–6, in parallel |
| 1–2 | Four parallel tracks: **A** data and the learning engine; **B** Juku's MCP server, identity, delegation and guardrails; **C** the thin app, consent, privacy and the frontend; **D** monitoring, CI and fitness functions. The eval tasks and fixtures are written first in each track |
| 2–3 | **E:** the agent pipeline and memory, which need A and B; the chat; the attack suite |
| 3 | The paid evals (launch gate), the deploy through Arthur, dogfooding with on-demand runs |
| 4 | Launch, as soon as the launch gate passes |

**Checks are standard procedure** ([standard-checks.md](standard-checks.md)).
Every step ends with its checks, and a failed check stops the step. That
is how a rushed build stays safe.

**What rushing doesn't change:**
- the gates before building;
- the guardrail, isolation and delegation tests;
- the privacy Musts;
- the launch gate (Q1 and MEM1 ≥ 90%);
- Arthur's OK on each paid run;
- the honesty rule.
