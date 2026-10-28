# Standard Checks: Verify at Every Step

The build is rushed (Phase 2, Time budget), so checking is standard
procedure, not something done at the end.

**The rule:** every step ends with its checks. **A failed check stops the
step.** Nothing moves to the next step, the next slice, a paid run, the
server or a publish until it passes, or until Arthur explicitly accepts the
failure. Every failure and its cause goes in JOURNEY.

## 1. Every commit (automatic, $0)

One command, `make check`, runs locally as a pre-commit hook and again in
CI. A red result blocks the merge.

| Check | Tool |
|---|---|
| Lint and format | ruff |
| Types, strict on `src` | pyright |
| Fast tests | pytest |
| Fitness functions FF1–FF9, FF12 and FF13 (scale path) | pytest, Squawk, Lighthouse CI |
| Secrets in the diff | gitleaks |
| No content in records, traces or logs (FF9) | pytest |
| MCP tool schemas match their snapshots (FF5) | pytest |
| Guardrail, delegation and isolation suites (FF8) | pytest |

**Also, by hand, for every new test:** mutation-check it. Break the code
on purpose, see the test fail, then restore it. This is Arthur's standing
rule.

## 2. End of every slice

- [ ] `docs/guide.md` matches the code: the request flow (files and
      functions), the glossary and "where to change things" are updated in
      the same commit (Arthur's "code humans can read" rule).

- [ ] The slice's "Done when" in the [slice plan](slice-plan.md) is met,
      and is shown by a command or a test, not by reading the code.
- [ ] The full test suite passes, and mutmut has been run on the changed
      modules. Survivors are triaged or listed.
- [ ] The eval tasks and fixtures for the slice came before its code (the
      git log shows it: Phase 1, EDD1).
- [ ] The slice's docs are updated: README, the ADR, and JOURNEY for
      anything that went wrong.
- [ ] One conventional commit per logical step, on a branch, and nothing
      pushed. Arthur pushes.

## 3. Where something can go wrong: specific checks

| Step | What can go wrong | Check before moving on |
|---|---|---|
| Loading the dictionary | A corrupt or changed download; a partial load | Checksums match the recorded ones; row counts match the release's; a load into a fresh database gives identical counts |
| Mapping JLPT lists and Tatoeba to JMdict | Wrong or ambiguous matches that silently mislabel levels | The ambiguous and unmatched counts are reported; a sample of 30 is checked by hand |
| A dictionary upgrade | Known words pointing at removed entries | The unmapped count is 0, or listed; FF3 is green after the upgrade |
| A database migration | A lock on a large table; data loss | Squawk is clean; the migration is run on a copy of real-shaped data first; a backup is taken just before |
| Recommender or engine rules | A silent change in ranking or grading | The fixtures match exactly; any fixture change is in the same commit, with the reason |
| Juku's MCP server and tokens | One learner reaching another's data; a widened delegation | The M7 and ID2 suites pass, and are mutation-checked; spike 6's attempts are rerun |
| The gateway policy | A tool allowed by mistake | The allow-list diff is reviewed line by line; an "outside the list" call is refused in a test |
| A prompt change | Quality drops; cost creeps up | Token ceilings (FF6) pass; the scripted pipeline fixtures pass; then the harness gate (paid, with OK) |
| The report pipeline | A wrong number or a stale claim published | Planted bad reports are blocked in code; the fallback path is tested |
| Memory | A note stored without evidence, or in a forbidden category | The refusal fixtures pass; a weekly look at new notes |
| Deletion and export | Something left behind; another learner's data exported | After "Hapus data saya", a query finds 0 rows for that learner in every table; an export contains only that learner's rows |
| Consent text changes | Learners held to terms they didn't see | The version is bumped, and existing learners are asked again before their next activity |
| The frontend | Bundle bloat; a slow first load on phones | FF12 is green; spot-check on a throttled mid-range Android profile |
| Japanese input | Romaji or width variants missing words | Normalization fixtures (romaji, half-width, mixed) pass |

## 4. Before any paid model run

- [ ] Arthur's OK for this run, recorded with its purpose.
- [ ] The run first goes end to end with the scripted model at $0.
- [ ] The price table has been rechecked and its date updated.
- [ ] The budget left, by pool, has been read from the records and is
      enough for the run's estimate.
- [ ] A per-run cap is set (the harness's `--budget`), below the remaining
      pool.
- [ ] For measurements: the prediction or acceptance rule is committed
      before the run.
- [ ] Afterwards: the actual cost is recorded next to the estimate.

## 5. Before any server step (done by Arthur or the server session)

- [ ] The exact commands are drafted for Arthur, with what each one does.
      Security settings are never changed through another session.
- [ ] A rollback for each step is written down before it runs.
- [ ] A backup is taken, and restored once on the laptop to prove it
      works.
- [ ] The environment holds only the keys this service needs (listed and
      compared).
- [ ] Memory caps are in the compose file. `docker compose config` is
      clean.
- [ ] After the step: health check, smoke test, one end-to-end trace, and
      each alert fired on purpose.
- [ ] No server details go into any doc or commit.

## 6. During the window

**Daily, automatic** (an alert if any fails):
- the heartbeat;
- scheduled runs completed;
- budget by pool;
- tool error rates;
- detector flags;
- the audit-chain verification;
- FF3 (state matches a recompute) on production data;
- cross-learner refusals.

**Weekly, by Arthur** (a checklist in the repo, about 45 minutes):
- [ ] Every failure from the week categorised (Phase 1, F1).
- [ ] Categories seen 3 or more times turned into a task or fixture.
- [ ] 20 chat answers and 5 reports hand-graded against the rubrics.
- [ ] Every detector flag judged a true or false positive.
- [ ] New memory notes, and learners' corrections, looked at.
- [ ] Spend against plan; whether the Should features or the speaking
      partner can switch on (and the switch-on date recorded).
- [ ] The weekly evidence SQL run, its output committed, and the privacy
      check passed.

## 7. Before publishing anything

This covers the case study, a README, screenshots, a portfolio entry, or
a post.
- [ ] The privacy check (EV2) passes.
- [ ] Every number links to a file in the evidence folder. Nothing typed
      by hand.
- [ ] No nicknames, codes, question text or cells under 5 learners. Dates
      by week.
- [ ] No server details, and nothing about past security incidents.
- [ ] Screenshots checked by eye.
- [ ] Anything outward-facing (posts, messages, sign-ups) is drafted for
      Arthur, and Arthur does it.

## 8. Before touching git history or a remote

- [ ] Check what is already on the remote (`git ls-remote`) before any
      rewrite.
- [ ] Private notes stay git-ignored: `git check-ignore` on `private/` and
      any handover file.
