# Phase 1: Problem Brief

**Project:** Shiori (栞, a bookmark, or a small guidebook), an agentic
learning platform for Indonesian adults studying for the JLPT
(Japanese-Language Proficiency Test). It follows the pattern of
[Pitstop](https://github.com/NabilRobert/pitstop-crew-public), this time
for learning Japanese:
- **Facts in code:** SQL and deterministic code compute each learner's
  progress.
- **Agents on a schedule:** a small team of agents plans the learner's
  next week and writes their report in Indonesian.
- **A critic:** it checks every number and every word against the data,
  and code decides approval.
- **On demand:** an agentic chat that can see the learner's progress
  answers questions about words, kanji and their mistakes.
- **Memory:** the agents' long-term memory of each learner is structured
  and inspectable. The learner can see everything Shiori remembers about
  them, and correct or delete any of it ("Shiori ingat…").

All knowledge of Japanese comes from open dictionary data in Postgres,
reached only through MCP tools. It is the seventh portfolio piece and the
first with real users. It runs on the stack built so far:
- [MCP-backbone](https://github.com/NabilRobert/MCP-backbone): the
  read-only database MCP server, for the dictionary;
- [mcp-security-gateway](https://github.com/NabilRobert/mcp-security-gateway):
  in front of every MCP server;
- [agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness):
  the offline measurement;
- agent-observability (Project 6): the traces.

## Problem

**For the portfolio:**
- Every earlier project proves its claims, but none has a user other than
  Arthur.
- Pitstop showed an agent team running unattended, but on synthetic data
  for one operator.
- A reviewer can't yet see how agents and MCP tools behave when real
  people depend on them: who comes back, how good the outputs are, what
  breaks, and what changed because of it.

**For the learners:**
- **Language.** Indonesian JLPT learners mostly study from English-language
  dictionaries and apps, a second foreign language for many of them.
- **Trust.** General chatbots state kanji readings, meanings and JLPT levels
  fluently, and sometimes wrongly. A learner can't tell which, so they
  learn the mistakes.
- **No sense of progress.** Flashcard apps count reviews, not "how much of
  N4 do I actually know, and am I on pace for the exam?".

*To verify in slice 1, not assumed:* which tools learners in the chosen
group already use, and what they're missing. If one already does grounded
Indonesian progress reports, the positioning below changes.

## Users

| Party | Who | Wants |
|---|---|---|
| **Learners (primary)** | Indonesian adults (18+) preparing for N5–N3, in a study group Arthur joins as a member (he is studying Japanese himself) | To know what they know, what to study next and whether they're on pace, with correct answers in Indonesian |
| **Arthur (builder, also a learner)** | Uses it himself | Evidence for the portfolio, and a tool he uses. His use is recorded separately and **excluded from every adoption number** |
| **Reviewer / hiring team** | Japan-style employers | Proof that agents and the tools hold up with real users: numbers from records, failures and their fixes, privacy handled with care |

Recruitment is from groups where JLPT learners already gather (study
groups on WhatsApp, Telegram or Discord). Arthur does all outreach; drafts
are prepared for him.

## Positioning: what makes this one different

**The subject is the agents and the MCP tools under real use, not the
app.** The interface is kept thin. The work and the evidence are about:
- which tools the agents call, and how often those calls fail or are
  refused;
- how many calls an output takes;
- how often the critic catches a wrong claim;
- what changed when something was improved.

Tool monitoring is a core requirement, not an add-on. The idea (a study
app with AI) is common, so the idea isn't what is being shown. What is:
1. **Real users, with published numbers.** People, sessions, return rate,
   output quality, failures and cost come from the records. They are
   published even if the targets are missed.
2. **Outputs that are checked, not trusted.**
   - Facts come from audited, read-only queries over open dictionaries, and
     outputs cite the entries they used.
   - In the weekly report, every number must match the computed facts, and
     every word must exist at the stated level.
   - The critic finds the issues; code decides approval, as in Pitstop.
   - A report that can't pass is replaced by a plain, facts-only version,
     never published unchecked.
3. **Least privilege for agents, enforced by MCP and the gateway.**
   - Each agent has its own gateway key and tool allow-list.
   - A learner's data is reached only through Shiori's own MCP server,
     whose tools are bound to that learner's session. An agent working for
     one learner cannot read another's data, whatever it asks for.
4. **Agent memory you can see, check and delete.**
   - Long-term memory is a central agent topic of 2026, and the common
     complaint is that it's opaque.
   - Shiori's memory is Postgres tables, not a hidden vector store:
     - **what the learner knows**, computed from their activity;
     - **what happened**, the activity itself;
     - **short agent notes** on how they learn, such as "often confuses
       on and kun readings".
   - Agents read it only through Shiori's MCP server. They can only
     *propose* a note, and code accepts it only with evidence: the
     activity rows that support it.
   - The learner sees every item, with its evidence, and can remove it.
   - Memory quality is measured, using the categories the memory
     benchmarks (LongMemEval, LoCoMo) use: noticing when a fact changed,
     reasoning about time, and saying "I don't know" when memory has
     nothing.
5. **A closed loop.** A failure found in real use becomes a harness task,
   then a fix, then a measured before/after.
6. **Deterministic learning engine.** These are code, so they're testable
   to the exact row and cost no model call:
   - **progress:** coverage of each level's words and kanji;
   - **quizzes:** generated and graded in code;
   - **the word recommender:** "i+1", words that add at most one unknown
     kanji, ranked by how common they are and how many other words that
     kanji unlocks;
   - **reading practice:** example sentences where the learner knows every
     word but one;
   - **the exam-pace planner.**

   The agents add judgement and explanation on top, not facts.

## Success metrics

All are computed by committed SQL over the records and Project 6's traces.
The **measurement window** is the first 4 counted weeks after launch.
Arthur's own use is excluded from A1–A4 and L1–L2.

**Adoption**

| # | Metric | Target | Floor (still publishable) |
|---|---|---|---|
| A1 | Consenting users who did at least one activity (chat, quiz, reading, report opened) | ≥ 10 | 5 |
| A2 | Users active in at least 2 of the 4 weeks | ≥ 5 | 3 |
| A3 | Sessions (a run of activity with gaps under 30 minutes) | ≥ 80 | 30 |
| A4 | Week-1 users who return in week 2 or later | ≥ 40% | reported as is |
| A5 | Weekly reports opened by their learner | ≥ 50% | reported as is |

**The agent pipeline (the weekly report)**

| # | Metric | Target |
|---|---|---|
| P1 | Scheduled runs that complete, out of those due | ≥ 98%; every miss caught by the dead-man's switch |
| P2 | Reports published with a number not in the facts, or a word not in the data at the stated level | **0**, enforced in code and audited from the run records |
| P3 | The critic's behaviour: first-pass approval, revisions, and facts-only fallbacks, per agent and per week | Reported. A fallback rate above 10% triggers a "what changed" |
| P4 | Arthur's weekly hand check of 5 reports against a committed rubric (useful, correct, tone) | ≥ 4 of 5 |

**Chat quality**

| # | Metric | Target |
|---|---|---|
| Q1 | Offline: strict pass rate on the committed task set (~40 tasks with answers checkable from the data), via agent-eval-harness | ≥ 90% before launch, with pass^k reported. **Launch gate** |
| Q2 | Grounding: share of answers whose citations all match rows returned in the same turn (checked automatically, every answer) | ≥ 95% |
| Q3 | Meaning: of a weekly random sample of 20 answers, the share Arthur judges correct and well explained in Indonesian (rubric committed before launch) | ≥ 85% |
| Q4 | User rating: thumbs-up share of rated outputs, plus the rating rate | ≥ 75% up |
| Q5 | Latency, end to end | p50 ≤ 15 s, p95 ≤ 40 s (the harness measured a 13 s median on Pagila with the same model) |

**The learning engine**

| # | Metric | Target |
|---|---|---|
| E1 | Offline: exact output for committed fixture learners (recommender top 10, quiz grading, i+1 sentences, pace), checked by tests | 100%. A change to any rule updates its fixtures in the same commit |
| E2 | Uptake: share of recommended words marked known or saved within 7 days | Reported as is |
| E3 | Share of activity served with no model call (quizzes, reading, recommendations, plan) | Reported, with cost and latency against the chat path |

**Memory**

| # | Metric | Target |
|---|---|---|
| MEM1 | Offline: about 15 memory tasks in the benchmark categories (a fact that changed, such as a word marked known and then missed twice; time, such as "what did I miss last week?"; and abstention when memory has nothing), with gold answers from fixture learners | ≥ 90% |
| MEM2 | Notes proposed by agents that code rejects for missing or wrong evidence | Reported; every rejection categorised |
| MEM3 | Notes that learners remove or mark wrong: a proxy for memory precision | ≤ 20%, reported per week |
| MEM4 | Reports that state something contradicted by newer activity (stale memory) | **0**: high severity for the critic and in code |
| MEM5 | Reports whose plan uses the learner's memory (cites a mistake, a note or a recent activity row) | Reported |

**Learning (reported, never claimed as caused by Shiori)**

| # | Metric | Target |
|---|---|---|
| L1 | Change in level coverage (words and kanji known) per active learner over the window | Reported as a distribution, no target |
| L2 | Quiz accuracy on review items over time | Reported, no target |

**Tool health (monitoring)**

Per MCP tool, on both servers (MCP-backbone's `list_tables`,
`describe_table`, `sample_rows`, `run_query`; Shiori's own tools), per
agent and per hop (app → gateway → server → database). The sources are
the gateway's and MCP-backbone's audit logs, the app's per-call records
and the traces.

| # | Metric | Target |
|---|---|---|
| M1 | Calls, error rate and p50/p95 latency per tool and per agent, weekly | Reported; ≤ 2% errors per tool, excluding correct refusals |
| M2 | Refusals by layer: gateway policy, injection detector, SQL validator, cost check, row cap | All categorised. Each detector flag is reviewed by hand as a true or false positive (Tatoeba sentences are public, user-written text) |
| M3 | Tool calls per output, and the share spent exploring the schema | Weekly; at least one change that measurably lowers it |
| M4 | Recovery: failed `run_query` calls followed by a successful corrected query in the same turn | Reported |
| M5 | Outputs with one unbroken trace across all hops | ≥ 95% |
| M6 | Time from an outage, a missed scheduled run or a budget stop to Arthur being told | ≤ 15 min, tested on purpose before launch |
| M7 | Attempts to reach another learner's data through Shiori's MCP server | 0 succeed (tested before launch; refusals logged) |

**Failures and change**

| # | Metric | Target |
|---|---|---|
| F1 | Every failure categorised: error, timeout, gateway block, budget stop, uncited answer, critic fallback, missed run, thumbs-down | 100% |
| F2 | "What changed" write-ups: a failure category from real use → a new eval task or fixture → a fix → before/after on the offline score and the live metric. At least one is a tool-level change (a tool description, a view, a tool's scope), not a prompt tweak | ≥ 2 |

**Cost and safety**

| # | Metric | Target |
|---|---|---|
| C1 | Total model spend, project lifetime | ≤ $4.50 (the key cap); cost per report, per question and per session published |
| S1 | Writes reaching the dictionary database | 0 (MCP-backbone's audit log) |
| S2 | Personal data in public evidence | 0 (checked by a script before anything is published) |

**Honesty rule, committed in advance:** if adoption lands below the
floors, the write-up reports the real numbers and what was learnt about
recruiting. It doesn't stretch the window or count Arthur.

## Non-goals (current pass)

- **No course and no tutor.** It doesn't teach grammar lessons or grade
  free writing.
- **No full spaced-repetition scheduler.** The mistakes queue uses simple
  Leitner boxes in code. SM-2-style scheduling is out of scope.
- **No voice.** The speaking partner, if built, is text only (Phase 2,
  Could). Voice recordings are sensitive data and costly to process.
- **No copyrighted study material.** No official JLPT past papers or
  textbook content; only openly licensed data.
- **No claims about results.** "Users passed the exam" or "Shiori improved
  learning" can't be attributed, so they aren't claimed (L1 and L2 are
  descriptive).
- **No open sign-up.** Access is by invite code, so cost and abuse stay
  bounded.
- **No mobile app, handwriting input or multi-tenancy.** WhatsApp trails
  the web page (Could).

## Decisions (settled with Arthur, 2026-10-27)

1. **Users:** Indonesian JLPT learners (N5–N3) in a study group, chosen
   over a developer community's resource directory and a workplace data
   assistant (Phase 5, ADR-001).
2. **Product:** an agentic learning platform on Pitstop's pattern, named
   **Shiori**.
3. **Focus:** the agents and MCP tools under real use. Tool monitoring is
   in scope here, because Project 6 deliberately stops at traces.
4. **Data:** open dictionary datasets (JMdict, KANJIDIC2, radical data,
   Tatoeba sentences, community JLPT-level lists) in their own Postgres,
   served through MCP-backbone.
5. **Channel:** a small web page first; WhatsApp later.
6. **Features, in priority order** (Phase 2, Must/Should/Could):
   1. the core agentic loop;
   2. reading practice;
   3. the exam planner and mistakes queue;
   4. the group digest and WhatsApp;
   5. a text speaking partner (worth it if there's room).
7. **Trend angle:** inspectable agent memory (checked against 2026
   sources, 2026-10-27). Running a Shiori quiz as an MCP App inside a
   learner's own assistant is a later Could.
8. **Budget:** $5 in total, a per-key cap of about $4.50, not topped up
   until building starts.
9. **Start:** only after the open server-security follow-ups are cleared
   and the gateway is pushed.

## Open questions

- **The study group:** which group(s) Arthur joins and recruits from.
- **Launch timing against the exam:** the December 2026 JLPT (first Sunday
  of December; confirm the date on jlpt.jp) drives study beforehand. A
  launch after mid-November mostly measures the post-exam lull (Phase 5,
  open decisions).

## Cost of doing nothing

The portfolio stays "careful infrastructure with no users". The question a
hiring team asks first, "has anyone used it?", stays unanswered.
