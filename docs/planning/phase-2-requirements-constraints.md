# Phase 2: Requirements & Constraints

Phases 3 and 4 are folded into this doc and Phase 5, as in Pitstop. The
build goes in slices ([slice plan](slice-plan.md)).

## Core scenario

1. A learner in the study group gets a personal invite code from Arthur.
   They open the web page, read a one-screen consent notice in Indonesian,
   confirm they're 18 or older, pick a nickname and their target level
   (N5–N3).
2. They ask, in Indonesian: "apa bedanya 見る dan 観る?", "kanji N4 yang
   pakai radikal 氵 apa saja?", "contoh kalimat untuk 勉強".
3. The model explores the dictionary through the gateway and MCP-backbone,
   answers in Indonesian, and cites the entries it used. The app checks
   each citation against the rows returned in that turn.
4. They press **Rekomendasi** and get 10 words to learn next, each with its
   reason, fetched with no model call. They mark words as known.
5. They rate answers with a thumbs up or down, optionally saying what was
   wrong.
6. Arthur watches tool health on a private dashboard and gets an alert if
   something breaks or the budget runs low. Weekly, he reviews failures and
   turns them into eval tasks.
7. Any time, the learner can press **Hapus data saya** and everything about
   them is gone.

## Requirements

**Chat (thin on purpose)**
- **C1.** A single web page: chat, a Rekomendasi button, the known-words
  list, ratings, and a settings panel (level, delete my data). The
  interface is in Indonesian.
- **C2.** The app is an MCP client of the gateway only. It never connects
  to a database directly, and the browser never holds a model or MCP key.
- **C3.** Answers state facts only from tool results, with citations
  (dictionary entry IDs, kanji or sentence IDs) in a fixed format. When the
  data doesn't have it, the answer says so ("tidak ada di data").
- **C4.** **Citation check:** after each answer, the app confirms that every
  cited ID appears in the rows the tools returned during that turn. An
  answer that fails is shown with an "unverified" label and counted (Q2).
- **C5.** A thumbs up or down on each answer, with an optional short reason
  chosen from a list (wrong meaning, wrong reading, wrong level,
  unclear, other).

**Dictionary data**
- **D1.** Its own Postgres database, loaded by committed scripts from the
  official releases: JMdict (words), KANJIDIC2 (kanji), KRADFILE/RADKFILE
  (radicals), Tatoeba (example sentences, including Indonesian
  translations where they exist) and community JLPT-level lists.
  Downloads aren't committed; their versions and checksums are.
- **D2.** Licences checked and attributed on an "about the data" page
  before launch. *To verify in slice 1:* the EDRDG licence (CC BY-SA)
  for JMdict, KANJIDIC2 and KRADFILE; CC BY 2.0 FR for Tatoeba; and the
  licence of whichever JLPT list is used. Since 2010 the official JLPT
  has published no word lists, so the levels are community estimates,
  and the page says so.
- **D3.** Served through MCP-backbone's "connect your own database", with a
  read-only login, on its own workspace and key, so its audit log is
  separate from the public demo's.
- **D4.** Schema comments and read-only views that make the data easier for
  a model to use (for example, one view joining a word's spellings,
  readings and first glosses). They are versioned, because changing them
  is a tool-level change measured in F2.

**Recommender**
- **R1.** Precomputed tables in the dictionary database: each word's kanji,
  each word's level and frequency band, and each kanji's leverage per
  level (how many common words at that level it appears in).
- **R2.** One committed, parameterised SELECT ranks words for a learner,
  given their level and known entry IDs (validated as integers by the app
  and capped in number). It must pass MCP-backbone's validator and cost
  check, and runs through the gateway like any other query.
- **R3.** Known kanji = every kanji of the levels below the learner's
  target level, plus the kanji of words they marked known. A word
  qualifies if it is at or below the target level, isn't known, and has at
  most one unknown kanji. The ranking and tie-breaks are written down in
  ADR-009 and pinned by fixture tests (Phase 1, R1).
- **R4.** Every suggestion carries its reason, generated from the row
  itself, not by the model.

**Monitoring (core, not an add-on)**
- **M1.** A per-call record for every MCP tool call the app makes: tool,
  path (chat or button), duration, outcome, error category, row count,
  and the trace ID. No arguments, SQL text or results in this record.
- **M2.** The gateway's audit log (JSONL, hash-chained) is imported into
  the monitoring schema on a schedule. The import verifies the hash chain
  first, and a broken chain is itself an alert.
- **M3.** MCP-backbone's audit log for this workspace is read through a
  read-only role, for refusal reasons by layer (validator, cost check, row
  cap).
- **M4.** A private dashboard over M1–M3 and the app's records:
  calls/errors/latency per tool, refusals by layer, tool calls per answer,
  recovery after a failed query, budget used, sessions per day.
  Dashboards are provisioned from committed files. **No panel ever shows a
  nickname, question text or anything about one user**, so a screenshot is
  safe to publish by construction.
- **M5.** Alerts to Arthur only: the app's heartbeat is stale for over 5
  minutes (a dead-man's switch, as in Pitstop); budget at 50%, 80% and
  100%; any tool's error rate over 5% in an hour; any injection-detector
  flag; a broken audit chain. Each alert is tested deliberately before
  launch (Phase 1, M6).
- **M6.** Every request is one trace across app → gateway → MCP-backbone,
  sent to Project 6's viewer, with content off by default (Project 6's
  convention).

**Spend control**
- **B1.** A budget guard in the app, checked before every model call:
  - a per-user cap of 20 questions a day;
  - a global cap of $0.20 a day;
  - a hard stop when the recorded user spend reaches its pool (see the
    [cost model](slice-plan.md#cost-model)).

  When a cap is reached, the app says so plainly and the Rekomendasi
  button keeps working, since it costs nothing.
- **B2.** Cost is computed from recorded token counts and a committed price
  table with its source and the date it was checked, the harness's
  `prices.yaml` convention. It errs high (cached input charged at full
  price).
- **B3.** The Sumopod key's own cap (about $4.50) is the last line, not the
  first.

**Evidence and docs**
- **E1.** Every published number comes from a committed SQL file run against
  the records, with its output committed, as in Pitstop.
- **E2.** A privacy check runs before anything is published: no nicknames,
  invite codes, question text, timestamps finer than a day, or groups
  smaller than 5 users (S2).
- **E3.** The case study, a JOURNEY log, and a portfolio entry in EN, JA
  and ID (handed to the site session; this repo doesn't edit the site).

## Privacy

The data is low-risk (questions about Japanese words), but it belongs to
real people, so it gets the care Phase 1 promises. Indonesia's Personal
Data Protection Law (UU PDP, Law 27/2022) is the frame: consent for a
stated purpose, access, deletion and withdrawal. This is design care, not
legal advice.

**Consent**
- A one-screen notice in plain Indonesian, shown before the first question,
  with a separate tick for each of: using the service; anonymous aggregate
  numbers appearing in Arthur's public portfolio; and (optional, off by
  default) letting a specific answer be quoted, decided per message when
  rating.
- **18+ only.** Many JLPT learners are school students; under UU PDP a
  child's data needs a parent's consent. Requiring 18+ keeps it simple,
  and the study-group recruitment targets adults.
- Withdrawal is "Hapus data saya", at any time.
- The consent text and its version are committed. Each user's record keeps
  the version they accepted and when.

**What is stored**

| Stored | Why | Not stored |
|---|---|---|
| Nickname (the notice suggests not using a real name) | To show in the page only | Real name, email, phone number |
| Hash of the invite code | Login | The code itself |
| Target level; entry IDs marked known | The recommender | Free-text notes |
| Questions and answers (text) | Showing history; Arthur's weekly review of failures | Anything outside the app |
| Ratings and reason chosen; quote permission | Q3/Q4 | |
| Timestamps, token counts, cost, tool-call records, trace IDs | Metrics, budget, monitoring | Tool arguments or results in traces (content off) |
| | | IP addresses: the site's access log is configured not to keep them, or to keep them for 7 days at most (decided at deploy) |

**Retention**
- Question and answer text: deleted 60 days after the measurement window
  closes. The only longer-lived copy is the anonymised aggregates.
- Tool-call records and metrics: kept without text; the user ID is removed
  at the same 60-day point.
- Traces: Project 6's retention period. No content, only a pseudonymous
  user hash.
- Backups: rolling 7 days, encrypted, so deleted data leaves the backups
  within 7 days.

**Deletion**
- "Hapus data saya" deletes the user's rows (cascading over history,
  ratings and known words) immediately, and tells them about the 7-day
  backup tail.
- Their tool-call records stay, with the user ID removed, so totals still
  add up.
- Arthur can do the same on request for someone who has lost their code.

**Public evidence**
- Aggregates only, never below 5 users in any cell; dates by week.
- Example questions are published only if the user ticked the quote
  permission for that message, and then without the nickname.
- Dashboards' screenshots are safe by construction (M4), and are still
  checked by eye.
- The privacy check (E2) runs before every publish.

**WhatsApp (later)**
- Phone numbers are personal data: they'd be hashed, with a separate
  consent notice.
- That, plus Meta's business verification, is why it trails the web page.

## Non-functional

- **Footprint:** it shares a small server, so every container has a memory
  cap. The dashboard tool's idle memory is measured and published, as
  Project 6 does for its viewer.
- **Latency:** p50 ≤ 15 s, p95 ≤ 40 s (Phase 1, Q5). The page shows
  progress while tools run.
- **Availability:** best effort, but every outage is noticed (M5) and
  counted.
- **Security:** the gateway allows this app's key only MCP-backbone's read
  tools, on this workspace. A new key for every secret, and nothing
  reused. Invite codes are random and single-person.
- **A reviewer gets it in about 15 minutes** from the README and the case
  study.

## Constraints

- **Budget:** $5 in total, a key cap of about $4.50. Not topped up until
  building starts. No paid model calls before then. Eval runs and launch
  each need Arthur's OK.
- **Gates before building:** the open server-security follow-ups are
  cleared (key rotations, key-only SSH on the second server), and the
  gateway is pushed. Nothing is planned to start sooner.
- **The gateway has no per-key rate limit yet.** It's listed under the
  gateway's "Next". Until it exists, rate limits live in the app (B1), and
  the gateway does auth, the tool allow-list, detection and audit.
- **Depends on Project 6** for the trace viewer. If it isn't deployed when
  this launches, traces wait, and M5/M6 rely on the app's own records.
- **Server work goes through Arthur** or the server's own session. No server
  details in public writing.
- **Outreach is Arthur's:** joining the group, posting, sending codes.
  Drafts are prepared for him.
- **Timing:** the December 2026 JLPT (confirm the date on jlpt.jp) drives
  study. A launch after mid-November mostly measures the post-exam lull.

## Must / Should / Could

| | Item |
|---|---|
| **Must** | C1–C5: thin chat, gateway only, cited answers, the citation check, ratings |
| **Must** | D1–D3: dictionary loaded by scripts, licences attributed, served through MCP-backbone read-only |
| **Must** | R1–R4: the recommender, with fixture tests |
| **Must** | M1, M4, M5, M6: per-call records, the dashboard, alerts (tested), traces |
| **Must** | B1–B3: budget guard, costed from a sourced price table, key cap |
| **Must** | Privacy as above: consent, 18+, stored/not stored, retention, self-serve deletion, public-evidence check |
| **Must** | The offline task set (~40 tasks) passing Q1 before launch |
| **Must** | E1, E2: evidence by committed SQL; the privacy check |
| **Should** | M2, M3: the gateway audit import with chain verification; MCP-backbone refusal reasons |
| **Should** | D4: views and schema comments, versioned |
| **Should** | E3: case study, JOURNEY, portfolio entry |
| **Should** | The gateway's per-key rate limit (built in the gateway repo, Arthur's call) |
| **Could** | A dedicated recommender MCP tool on a second small server behind the same gateway, measured against the SQL path (tool calls, accuracy, latency) |
| **Could** | gpt-5-nano as a cheaper fallback near the budget's end, measured as a "what changed" |
| **Could** | WhatsApp, after the web page has run its window |
| **Won't** | Open sign-up, spaced repetition, audio, copyrighted study material, a mobile app |

## Rough effort

About 2–3 weeks of building, then the 4-week window:
- data and recommender: 2–3 days;
- the thin app with consent and deletion: 3–4 days;
- monitoring and alerts: 2 days;
- the eval task set: 1–2 days;
- deploy and dogfood: 2–3 days, mostly waiting on server steps;
- the window: 4 weeks, with weekly reviews;
- evidence and write-up: 2–3 days.
