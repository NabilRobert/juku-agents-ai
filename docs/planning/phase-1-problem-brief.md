# Phase 1: Problem Brief

**Project:** a small AI assistant for Indonesian learners studying for the
JLPT (Japanese-Language Proficiency Test). It answers questions about
vocabulary, kanji, readings and example sentences in Indonesian, from open
dictionary data held in Postgres. Every fact it states comes from a
read-only query and cites the entry it came from.

It is the seventh portfolio piece and the first with real users. It runs on
the stack built so far:
- [MCP-backbone](https://github.com/NabilRobert/MCP-backbone): the database
  MCP server;
- [mcp-security-gateway](https://github.com/NabilRobert/mcp-security-gateway):
  the gateway in front of it;
- [agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness):
  the offline measurement;
- agent-observability (Project 6): the traces.

## Problem

**For the portfolio:** every earlier project proves its claims, but none
has a user other than Arthur. Pitstop ran for 11 weeks on synthetic data
for one operator. A reviewer can't yet see how this stack behaves when
real people ask real questions: how many come back, how good the answers
are, what breaks, and what changed because of it.

**For the users:** Indonesian JLPT learners mostly study from
English-language dictionaries and apps, plus general chatbots. Two gaps:
- **The language.** Explanations and glosses are mostly in English, a second
  foreign language for many learners.
- **Trust.** A general chatbot states kanji readings, meanings and JLPT
  levels fluently, and sometimes wrongly, with nothing to check them
  against. A learner can't tell which answers are wrong, so they learn the
  mistakes.

*To verify in slice 1, not assumed:* which existing tools (dictionary
apps, study apps, chatbots) Indonesian learners in the chosen group already
use, and what they're missing. If a tool already does grounded Indonesian
answers by JLPT level, the positioning below changes.

## Users

| Party | Who | Wants |
|---|---|---|
| **Learners (primary)** | Indonesian adults (18+) preparing for JLPT N5–N3, in a study group Arthur joins as a member (he is studying Japanese himself) | Quick, correct answers in Indonesian: "what does this word mean", "which N4 kanji use this radical", "show me example sentences at my level" |
| **Arthur (builder, also a learner)** | Uses it himself | Evidence for the portfolio; a tool he actually uses. His own use is recorded separately and **excluded from every adoption number** |
| **Reviewer / hiring team** | Japan-style employers | Proof that the stack holds up with real users: numbers from records, failures and their fixes, privacy handled with care |

Recruitment is from groups where JLPT learners already gather (study
groups on WhatsApp, Telegram or Discord). Arthur does all outreach; drafts
are prepared for him.

## Positioning: what makes this one different

**The subject is the MCP tools under real use, not the app.** The app is
kept thin on purpose: a chat page, consent and a budget guard. The work
and the evidence are about how the tools behave when real people's
questions reach them through the gateway: which tools get called, how
often they fail or are refused, how many calls an answer takes, and what
changed when they were improved. Tool monitoring is therefore a core
requirement, not an add-on.

The idea (a study chatbot) is common, so the idea isn't what is being
shown. What is:
1. **Real users, with published numbers.** People, sessions, return rate,
   answer quality, failures and cost come from the app's own records, and
   they are published even if the targets are missed.
2. **Answers that are checked, not trusted.**
   - Facts come from audited, read-only SQL over open dictionaries, and
     each answer cites the entries it used.
   - The app checks every citation against the rows the query actually
     returned. An answer whose citations don't check out is marked
     unverified.
   - So "how often is it wrong without anyone knowing?" becomes a number.
3. **A closed loop.** A failure found in real use becomes a harness task,
   then a fix, then a measured before/after. The "what changed" is shown
   with data, the way Pitstop showed its failures.

## Success metrics

All are computed by committed SQL over the app's records and Project 6's
traces, as in Pitstop. The **measurement window** is the first 4 weeks
after launch. Arthur's own use is excluded from A1–A4.

**Adoption**

| # | Metric | Target | Floor (still publishable) |
|---|---|---|---|
| A1 | Consenting users who asked at least one question | ≥ 10 | 5 |
| A2 | Users active in at least 2 of the 4 weeks | ≥ 5 | 3 |
| A3 | Sessions (a session is a run of questions with gaps under 30 minutes) | ≥ 80 | 30 |
| A4 | Week-1 users who return in week 2 or later | ≥ 40% | reported as is |

**Quality**

| # | Metric | Target |
|---|---|---|
| Q1 | Offline: strict pass rate on the committed task set (~40 tasks whose answers are checkable from the data), via agent-eval-harness, before launch | ≥ 90%, with pass^k reported. **Launch gate.** |
| Q2 | Grounding: share of answers whose citations all match rows returned in the same turn (checked automatically, every answer) | ≥ 95% |
| Q3 | Meaning: share of a weekly random sample of 20 answers that Arthur judges correct and well explained in Indonesian (rubric committed before launch) | ≥ 85% |
| Q4 | User rating: thumbs-up share of rated answers, plus the rating rate | ≥ 75% up |
| Q5 | Latency, end to end | p50 ≤ 15 s, p95 ≤ 40 s (the harness measured a 13 s median on Pagila with the same model) |

**Tool health (monitoring)**

Reported per MCP tool (`list_tables`, `describe_table`, `sample_rows`,
`run_query`) and per hop (app → gateway → MCP-backbone → database), from
the gateway's and MCP-backbone's audit logs and the traces.

| # | Metric | Target |
|---|---|---|
| M1 | Calls, error rate and p50/p95 latency per tool, per week | Reported; error rate ≤ 2% per tool, excluding refusals that were correct |
| M2 | Refusals by layer: SQL validator, cost check, row cap, gateway policy, injection detector | Every refusal categorised; each detector flag reviewed by hand as a true or false positive |
| M3 | Tool calls per answer, and the share spent exploring the schema rather than answering | Reported weekly; at least one change that measurably lowers it (counts towards F2) |
| M4 | Recovery: share of failed `run_query` calls followed by a corrected query that succeeds in the same turn | Reported |
| M5 | End-to-end traceability: share of answers with one unbroken trace across all hops | ≥ 95% |
| M6 | Alerting: time from an outage or a budget stop to Arthur being told | ≤ 15 min, checked by a deliberate test before launch |

**Failures and change**

| # | Metric | Target |
|---|---|---|
| F1 | Every failure is categorised: error, timeout, gateway block, budget stop, uncited answer, thumbs-down | 100% categorised |
| F2 | "What changed" write-ups: a failure category from real use → a new eval task → a fix → before/after on Q1 and on the live metric. At least one is a tool-level change (a tool description, a read-only view, a schema comment), not a prompt tweak | ≥ 2 |

**Cost and safety**

| # | Metric | Target |
|---|---|---|
| C1 | Total model spend, project lifetime | ≤ $4.50 (the key cap); cost per session reported |
| S1 | Writes reaching the dictionary database | 0 (MCP-backbone's audit log) |
| S2 | Personal data in public evidence | 0 (checked by a script before anything is published) |

**Honesty rule, committed in advance:** if adoption lands below the
floors, the write-up reports the real numbers and what was learnt about
recruiting, rather than stretching the window or counting Arthur.

## Non-goals (current pass)

- **No course and no tutor.** It doesn't teach grammar lessons, grade
  writing or do spaced repetition.
- **No copyrighted study material.** No official JLPT past papers and no
  textbook content. Only openly licensed data.
- **No claims about JLPT results.** "Users passed the exam" can't be
  attributed to the tool, so it isn't claimed.
- **No WhatsApp in the first version.** The web page comes first; WhatsApp
  trails (Phase 2, Could).
- **No open sign-up.** Access is by invite code, so cost and abuse stay
  bounded.
- **No mobile app, audio, handwriting input or multi-tenancy.**

## Decisions (settled 2026-10-27)

1. **Users:** Indonesian JLPT learners (N5–N3) in a study group, chosen
   over a developer community's resource directory and a workplace data
   assistant (Phase 5, ADR-001).
2. **Data:** open dictionary datasets (JMdict, KANJIDIC2, radical data,
   Tatoeba example sentences and community JLPT-level lists) in their own
   Postgres, served through MCP-backbone.
3. **Channel:** a small web page first; WhatsApp later.
4. **Budget:** $5 in total; a per-key cap of about $4.50; not topped up
   until building starts.
5. **Start:** only after the open server-security follow-ups are cleared
   and the gateway is pushed.
6. **Focus:** the MCP tools under real use. Tool monitoring (per-tool
   metrics, dashboards and alerts) is in scope here, because Project 6
   deliberately stops at traces (Phase 5, ADR-008).

## Open questions (for Phase 2)

- **The study group:** which group(s) Arthur joins and recruits from.
- **Launch timing against the exam:** the December 2026 JLPT (first Sunday
  of December; confirm the date on jlpt.jp) is a strong reason to study
  beforehand. If the launch slips past mid-November, the window falls
  mostly after the exam, when study drops off.
- **Name:** the product and repo names (proposed separately).

## Cost of doing nothing

The portfolio stays "careful infrastructure with no users". The question a
hiring team asks first, "has anyone used it?", stays unanswered.
