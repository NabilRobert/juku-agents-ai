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
