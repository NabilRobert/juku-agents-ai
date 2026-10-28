# Journey

What went wrong while building, and what changed because of it
(standard-checks.md: "every failure and its cause goes in JOURNEY").

## Track D: the skeleton, CI and monitoring (2026-10-28)

- **A commit went in with a red check.** The commit command was chained
  after a filtered `make check` whose pipe ended in `tail`, so its exit
  status was `tail`'s, not make's. pyright had failed on one column type.
  The commit was local and unpushed, so it was fixed and amended. The
  check is now run so that its own status gates the commit.
- **Squawk and gitleaks aren't installed on the laptop**, and installing
  them is a download outside ADR-025's approved list, so it waits for
  Arthur's OK. Until then `make check` skips them locally with a note, and
  CI, which installs both at pinned versions, runs them. FF4 has
  therefore not yet been run on a real Squawk.
- **Squawk would flag Alembic's own `alembic_version` table** (a varchar
  column, no `IF NOT EXISTS`). It isn't Juku's table, so `make
  migrations-lint` cuts that one statement before linting.
- **Grafana's provisioning was checked in the real image** (13.2.4, the
  spike-3 one, cached), not only by tests: the data source's `$__file{}`
  password, the dashboard, all six alert rules and the Telegram contact
  point loaded; each alert fired on purpose and cleared. Delivery to
  Telegram needs the real token, so it waits for slice 8.
- **mutmut, at the end of the track.** Run over the whole workspace, mutmut
  3 couldn't map `packages/<name>/src` to module names and ran no tests,
  so each package now has its own `[tool.mutmut]` and `make mutation`
  runs them one by one. juku-common: 165 of 194 mutants killed; juku-ops:
  218 of 229, then tests were added for the real gaps it showed (a JSON
  line that isn't an object, a recovery as the last line, the gateway's
  line format, wrong-typed fields, two logs side by side, a torn line
  mid-file, a bad timestamp). The survivors left are equivalent (a no-op
  `cast`, `strict=` on zips of equal length, the default text encoding)
  or only change an error message's wording.

## Track A: the data and the learning engine (2026-10-28)

- **A rewrite reintroduced a bug the spike had avoided.** Spike 2 split a
  word into letters under the alias `ch`; the production version named it
  `character`, which is also a column of the kanji table, so the
  "is it a kanji?" subquery compared the column with itself and every
  letter counted. The first test of the derived tables (`一つ` should
  have one kanji) caught it.
- **FF3 found a real disagreement on its first run.** The recompute
  counted a day on which a learner only unmarked a word as a day of
  activity, with all counts zero; the incremental path, correctly, made
  no row. The recompute now leaves unmarks out.
- **Two recompute queries were too slow at 5,000 learners.** Building the
  synthetic database showed a correlated subquery per word for the
  Leitner box, and one per learner and level for coverage, each scanning
  an unindexed temporary table: 16.5 s for 250 learners. Both became
  set-based (a window, and two grouped joins): about 4 s. FF3 stayed green
  across both changes.
- **A test leaked state into others.** A quiz test graded answers on a
  shared fixture learner, so whether another test saw an empty mistakes
  queue depended on the order. Tests that write now make their own
  learner, and the drift test deletes the learner it corrupts.
- **The incremental recommender is fast.** 4.4 ms for the 4,000-word
  learner against spike 2's 231 ms p95, because it now ranks a few hundred
  rows instead of re-deriving the known kanji on every call.
- **mutmut** runs on the engine's pure rules (`state.py`, `japanese.py`):
  89 of 99 mutants killed at first; the survivors showed untested counts on
  a wrong answer, `last_seen_at`, and romaji with a space. With those
  tests, 99 of 99. The database-backed modules would rebuild the test
  databases for every mutant, so their rules were broken by hand instead:
  eight in the engine (the candidates' affected words, kanji coverage,
  the same-day rule, the Leitner reset, the variety cap, the gap-first
  order, unmarking in the recompute, the plan's rounding) and one query
  for FF1. Each made a test fail.

## Track B: Juku's MCP server, identity and guardrails (2026-10-28)

- **Installing OpenJLPT's Python package was refused** by the session's
  permission check: it's a git dependency whose `setup.py` runs at
  install. Not worked around. `search_words` searches the same build in
  the dict database meanwhile (ADR-027), and the swap waits for Arthur's
  OK.
- **The in-memory MCP client couldn't live in a pytest fixture.** anyio's
  cancel scopes must be left in the task that entered them, and
  pytest-asyncio sets a fixture up and tears it down in different tasks.
  Each client now lives in a background task of its own for the test.
- **A lifespan wrapper called itself.** Wrapping the MCP SDK's lifespan
  looked it up at call time, after it had been replaced by the wrapper:
  a recursion at start-up, caught by the HTTP test. It's captured first
  now.
- **Mutation checks.** Disabling each of the token verifier's 21
  refusals in turn: 19 failed a test at first; a malformed token and a
  parent from another chain had none. With those, 21 of 21. The server's
  own four refusals, the caller binding and the replan cap: each fails a
  test when broken.
- **SAF1: 15 of 15 as predicted, both ways.** The two attacks predicted to
  succeed directly did, and none did through the patched gateway (and,
  rerun once the gateway merged P6, none through the real one either). The
  gateway's rules detector flagged none of the planted instructions; the
  defence was Juku's server refusing what they asked for.
- **G1 is checked, not claimed.** A guardrail harness lists every rule in
  guardrails.yaml's guardrail sections and fails make check if one has no
  test marked with it.

## Track C: the thin app, with chat on a scripted model (2026-10-28)

- **Every model in the tests is scripted.** Shiori runs on PydanticAI's
  `FunctionModel`, so the chat, its tools through Juku's MCP server, the
  budget guard and the citation check are all exercised at $0. Streaming
  needed a `stream_function` beside the plain one: without it, the
  streamed chat failed while the plain one passed.
- **OpenTelemetry allows one tracer provider per process.** The server's
  tests and the app's each wanted their own, and a second one is silently
  ignored. Tracing set-up moved to `juku_common/telemetry.py`, and the
  test kit has one shared span fixture.
- **Partitions are tables too.** Deletion and export find the learner's
  tables by their `learner_id` column, and `information_schema` lists each
  monthly partition as a table of its own, so events would have been
  counted twice. The code and its test read `pg_class` without partitions
  instead.
- **A test agreed with its mutant.** Making the per-learner daily cap
  count from midnight UTC instead of the learner's midnight survived: the
  test's two moments fell on the same day in both timezones. It now uses
  06:00 and 08:00 in Jakarta, which fall on two different days in UTC.
- **Mutation checks.** The budget guard's caps, the deletion's cascade,
  six points in the chat flow (moderation, the budget check, the citation
  check, the tool results it checks against, the per-call record, the
  usage record) and the pages' consent
  gate and CSRF check: each fails a test when broken. The consent gate had
  no test at first; one was added before checking it.
- **npm skipped Rollup's native binary** (npm's optional-dependency bug),
  so Vitest couldn't start after a clean install. Rollup is pinned
  through `overrides` instead.
- **A Vitest test found a hidden button.** An answer with no streamed
  text (a refusal, say) showed no rating buttons, because the answer only
  appeared once text arrived. It now appears when the stream is done.
- **FE7, measured:** the chat page loads 29.1 KB of JavaScript, the quiz
  28.7 KB, every other page 2.2 KB; the CSS is 2.2 KB (all gzipped).
  `make check` fails past the budget.
- **Not run here:** Lighthouse (FF12) needs Chrome, so it runs in CI
  only; the image's Python stages need base images that weren't cached,
  so only its Node stage was built.
- **Waiting on Arthur:** the moderation checker (until it's chosen, the
  checker flags nothing, and the distress path is tested with a stand-in),
  and a verified crisis line number for `JUKU_CRISIS_LINE`.

## Slice 4: memory (2026-10-29)

- **The MEM1 tasks came first,** in agent-eval-harness's own format (its
  validator accepts them), with four fixture learners. Each task's gold
  answer is reference SQL over the fixtures; a $0 test replays each
  fixture through production code and checks that the tools Shiori must
  call show what the answer needs. All 15 pass. Shiori answering them is
  the paid run, slice 7.
- **A fixture hit the partitions.** Hana's stale note was first dated in
  September, but the event table's partitions start in October 2026. Her
  note now dates from early October, and it lapses because newer right
  answers contradict it, not because of its age.
- **A commit went in after a red check, again.** Under heavy load from
  another project's containers, the check timed out in the synthetic
  database's fixture; the commit command sat on a new line, not after the
  check's `&&`, so it ran anyway. It was undone locally (nothing had been
  pushed) and redone after a green check, and commits now run from a
  script with `set -e`, behind the check.
- **The synthetic database rebuilt on every change to juku-data,** about
  eight minutes, because its cache key hashed the whole package. It now
  hashes what it depends on: the migrations, the engine, the dictionary
  loader, normalization and the generator.
- **Mutation checks.** mutmut on the evidence rules: 120 of 148 mutants
  killed at first. The 28 survivors showed untested recurrence for three
  of the four categories, right answers on another word or kind
  counting as a contradiction, and the 30-day edge. With those tests, 146
  of 148; the two left are equivalent (a single quiz kind is always a
  proper subset of the two, and an answer at the very instant of the last
  miss). By hand, fourteen breaks in the database-backed code, the
  migration, the page, the job and the tool: each fails a test.
- **What's checked where.** Code refuses a forbidden category, a note
  whose text is about someone's life, evidence that isn't this learner's
  or doesn't show the pattern, a kind of note the learner removed in the
  last 30 days, a 13th note and a duplicate. The table refuses a category
  the rule file doesn't allow. Refusals are counted by reason, never with
  their text (MEM2).

## Slice 6, the pipeline half (2026-10-29)

- **The fixtures came first:** 10 learners (MEM1's four and six more, one
  in Tokyo whose week turns at her own midnight), each with gold facts from
  one reference query, and six planted bad outputs. A scripted crew reads
  the JSON facts the run sends it: the faithful crew's reports are
  published as written; every planted output is blocked in code although
  Tadashi is scripted to approve it, and the learner gets the facts-only
  report. That is slice 6's "Done when": a planted bad number, an off-level
  word and a stale claim are each blocked in code.
- **Pitstop's critic, ported.** Severities, approval decided in code, and
  at most 2 revisions, from gads-case-study e15697e (critic.ts and
  criticLoop.ts); the feedback job from its weeklyFeedback.ts. Juku adds
  code's own checks, which block whatever Tadashi says.
- **A stale claim the facts couldn't see.** The planted case cites a note
  Gita removed the day before the run, so it was never in the run's facts,
  and the first version called it an unknown citation: blocked, but not
  for the right reason. Removed, wrong and lapsed notes are never shown to
  agents, so code now checks citations against them too, and calls a hit
  what it is: stale memory (MEM4).
- **A planted number had to be one no fact holds.** The first planted
  report said 12 quizzes; a candidate's leverage could be 12, and any
  number in the facts is allowed. It says 987 now.
- **Without a model key** the app's stand-in model answers in plain text,
  which can't be a plan: the run now ends in the facts-only report instead
  of failing.
- **The dead-man's switch** is two alerts: the existing "missed run" for the
  hourly cron job (`run-weekly` in expected_jobs), and a new one counting
  learners with no report an hour after their Sunday 18:00
  (`monitoring.pipeline_overdue_at`). Both are queries Grafana runs as
  `grafana_reader`; the Telegram side is checked on the server (slice 8).
- **Mutation checks:** 26 breaks, by hand, in the checks, the approval, the
  revisions, the run claim and lease (FF7), the budget, the schedule, the
  replan's delegation, the feedback job's privacy, the inspector's access
  and the overdue function: each fails a test.
- **Not done here:** FF6 (token ceilings) needs a tokenizer, and none is on
  ADR-025's approved list; it stays pending for Arthur. The paid runs are
  slice 7, with Arthur's OK.

## The consent gate (2026-10-29)

- **Reports and chat only on the current notice.** The pages already sent a
  learner without current consent to the notice; the weekly run didn't. Now
  it skips them, records why (`app.pipeline_skips`, "consent_outdated"),
  and their queued replans wait; the next hourly run after they accept
  gives them their report. A recorded skip isn't an overdue run, and a run
  that goes ahead clears it, so a later failure still alerts.
- **The tests' learners now consent, as real ones do,** or the gate would
  have skipped every fixture.
- **Mutation checks:** six breaks (the run's check, recording and clearing
  the skip, the replans' check, the overdue function, the pages' gate),
  each failing a test.
