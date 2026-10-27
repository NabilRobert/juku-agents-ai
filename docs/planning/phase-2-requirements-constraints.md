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
- **LE4. Reading practice (Should):** Tatoeba sentences, linked to JMdict
  entries through Tatoeba's word index, in which every word but one is
  known. Coverage of the index is measured in spike 4.
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
- **SM4.** **Agents have no write tools at all.** When the chat suggests
  marking a word known, it shows a button; the learner's click writes,
  through the app. That is approval decided in code, as in Pitstop.
- **SM5.** It sits behind the gateway like MCP-backbone, with its own audit
  log, and spans that follow Project 6's conventions.

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

| Agent (names proposed) | Role | Tools through the gateway |
|---|---|---|
| **Shiori** (chat) | Answers on demand, in Indonesian, with citations | MCP-backbone read tools (dictionary); Juku's server, scoped to this learner |
| **Hana** (planner) | Picks next week's focus (words, kanji and mistakes to review) **only from candidates the engine computed**, says why, and may propose notes (MEM-R2) | Juku's server, scoped to this learner and run |
| **Kenta** (writer) | Writes the weekly report (≤ 300 words, Indonesian) from the facts and Hana's plan | none: works only from what it is given |
| **Rin** (critic) | Reviews Hana's and Kenta's outputs against the facts they were given, listing issues with a severity | none |

- **AG1. The pipeline** runs per learner: facts → Hana → Rin → Kenta → Rin.
  - An output passes only if Rin reports no high-severity issue. High
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
- **AG2. Scheduling** by external cron (as in Pitstop), Sunday 18:00 WIB.
  - Each run records its start and end.
  - A dead-man's switch alerts if a due run hasn't completed within an
    hour.
- **AG3. Run records:** `pipeline_runs`, `agent_outputs` and
  `critic_reviews`, plus a Run Inspector page for Arthur only. It shows
  each run's facts, every model call, each review and the decision.
- **AG4. Feedback job (Should).** Weekly, it reads recurring patterns in
  Rin's issues and drafts prompt changes for Arthur. **Nothing is ever
  applied automatically.**
- **AG5. Chat:**
  - Answers state facts only from tool results, with citations in a fixed
    format.
  - The app checks every cited ID against the rows returned in that turn,
    and labels an answer that fails "unverified" (Phase 1, Q2).
  - When the data doesn't have it, the answer says "tidak ada di data".

**The interface (thin on purpose)**
- **UI1.** Server-rendered pages, in Indonesian: Chat, Kuis, Rekomendasi,
  Bacaan, Rencana, Laporan, **Shiori ingat…** (memory), and Settings
  (level, exam date, delete my data).
- **UI2.** The browser holds no model or MCP key. The app reaches data only
  through the gateway, except its own writes from learner clicks.
- **UI3.** A thumbs up or down on chat answers and reports, with an
  optional reason chosen from a list.

**Dictionary data**
- **D1.** Its own Postgres database, loaded by committed scripts from the
  official releases: JMdict, KANJIDIC2, KRADFILE/RADKFILE, Tatoeba (with
  its word index, and Indonesian translations where they exist) and a
  community JLPT list. Downloads aren't committed; their versions and
  checksums are.
- **D2.** Licences checked and attributed on an "about the data" page
  before launch. *To verify in slice 1:* the EDRDG licence (CC BY-SA) for
  JMdict, KANJIDIC2 and KRADFILE; CC BY 2.0 FR for Tatoeba; and the JLPT
  list's licence. The official JLPT has published no word lists since
  2010, so the levels are community estimates, and the page says so.
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

**Public evidence**
- Aggregates only, never below 5 learners in any cell; dates by week.
- An output is quoted only with that message's quote permission, and
  without the nickname.
- Dashboard screenshots are safe by construction (M4), and are still
  checked by eye.
- The privacy check (EV2) runs before every publish.

## Non-functional

- **Footprint:** a small shared server, so every container has a memory
  cap. Grafana's idle memory and the MCP server's are measured and
  published.
- **Latency:** chat p50 ≤ 15 s and p95 ≤ 40 s; the $0 pages under 1 s.
  Reports are written ahead of time, so they load at once.
- **Availability:** best effort, but every outage and missed run is noticed
  (M5) and counted.
- **Security:**
  - each agent has its own gateway key and allow-list;
  - agents have no write tools;
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
  study. A launch after mid-November mostly measures the post-exam lull.

## Must / Should / Could

| | Item |
|---|---|
| **Must** | LE1–LE3, LE7: progress, quizzes, the recommender, with fixtures |
| **Must** | SM1–SM5: Juku's MCP server, scoped by session, read-only, behind the gateway |
| **Must** | MEM-R1–R6: structured memory, evidence-checked notes, learning-only categories, consolidation, the "Shiori ingat…" page |
| **Must** | AG1–AG3, AG5: the weekly pipeline with critic and code approval, scheduling with a dead-man's switch, run records, the cited chat |
| **Must** | UI1–UI3; D1–D3; M1, M4–M6; B1–B3 |
| **Must** | Privacy as above: consent, 18+, stored/not stored, retention, self-serve deletion, public-evidence check |
| **Must** | Before launch: the offline chat task set (~40 tasks) at Q1 ≥ 90%; about 15 memory tasks at MEM1 ≥ 90%; pipeline fixtures for 10 learners |
| **Must** | EV1, EV2 |
| **Should** | LE4: reading practice (i+1 sentences) |
| **Should** | LE5, LE6: the pace planner and the mistakes queue |
| **Should** | AG4: the feedback job; M2, M3: the audit imports; D4: views and schema comments |
| **Should** | EV3: case study, JOURNEY, portfolio entry |
| **Should** | The gateway's per-key rate limit (built in the gateway repo; Arthur's call) |
| **Could** | X1: the group digest; X2: WhatsApp delivery; X3: the text speaking partner |
| **Could** | X4: a Juku quiz as an MCP App, so a learner can use it inside their own assistant. It needs OAuth on Juku's MCP server, and its own consent wording |
| **Could** | gpt-5-nano as a cheaper fallback near a pool's end, measured as a "what changed" |
| **Won't** | Voice, open sign-up, full spaced repetition, free-writing grading, copyrighted material, a mobile app |

## Rough effort

About 5–6 weeks of building, then the 4-week window:

| Work | Estimate |
|---|---|
| Data | 2 days |
| The learning engine (Must parts) | 3–4 days |
| Juku's MCP server | 2–3 days |
| The thin app with consent and deletion | 3–4 days |
| The agent pipeline and scheduling | 4–5 days |
| Memory (notes, checks, consolidation, the page) | 2–3 days |
| Monitoring and alerts | 2 days |
| Eval set and pipeline fixtures | 2 days |
| Deploy and dogfood | 3 days, mostly waiting on server steps |
| The Should items | another 4–5 days, built if they fit before launch; otherwise during the window, behind a flag, so they don't change the metrics mid-window unannounced |
| Evidence and write-up | 3 days |
