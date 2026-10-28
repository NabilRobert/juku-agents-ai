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
