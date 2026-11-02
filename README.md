# Juku

塾 (*juku*): a Japanese cram school, where staff coach students towards an
exam.

An agentic learning platform for Indonesian adults studying for the JLPT,
levels N5 to N2. Its staff is a small crew of agents, each named with a
pun on its job:
- **Shiori** (栞, a bookmark: it keeps your place): the lead, and the
  keeper of each learner's memory;
- **Keiko** (稽古, practice; and an echo of 計画, a plan): plans each week;
- **Nikki** (日記, a diary): writes the weekly report;
- **Tadashi** (正しい, correct): the critic;
- **Susumu** (おすすめ, a recommendation; 進む, to advance): the word
  recommender. It's code, not an agent.

It follows the pattern of
[Pitstop](https://github.com/NabilRobert/pitstop-crew-public), this time
for learning Japanese:
- code computes each learner's progress;
- a small agent team plans their week and writes their report in
  Indonesian;
- a critic checks every number and word against the data, and code
  decides approval.

An agentic chat answers questions with citations. The agents' memory of
each learner is structured and inspectable: learners see what Shiori
remembers about them, with its evidence, and can remove it.

All knowledge of Japanese comes from [OpenJLPT](https://github.com/evanclan/OpenJLPT)
(CC BY-SA 4.0: JLPT words linked to JMdict, kanji, grammar points and
Tatoeba examples), reached only through MCP tools.

It puts the 2026 agent topics to work where they fit:
- every agent has its own identity, and delegation chains (learner →
  agent → agent → tool) can only narrow;
- guardrails are code, each with a test;
- evals are written before the agents;
- a safety eval targets Juku's own attack surfaces;
- a written map shows where humans decide.

It claims memory, not continual learning.

It is the seventh piece of a portfolio, and the first with real users. The
subject is the agents and MCP tools under real use; the app is kept thin.
It runs on the same stack as the others:
- [MCP-backbone](https://github.com/NabilRobert/MCP-backbone): the
  read-only database MCP server, for the dictionary;
- [mcp-security-gateway](https://github.com/NabilRobert/mcp-security-gateway):
  in front of every MCP server;
- [agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness):
  measures quality offline;
- agent-observability (Project 6): traces each request and run.

**Status: building.** Track D (the skeleton, CI and monitoring), track A
(the data and the learning engine), track B (Juku's MCP server, identity
and guardrails), track C (the thin app, with chat on a scripted model)
slice 4 (memory: evidence-checked notes the learner can correct) and
slice 6's pipeline half (Keiko, Nikki and Tadashi on scripted models, with
code's own checks) are in; evals with real models, then deploying, follow
([slice plan](docs/planning/slice-plan.md)). Nothing is deployed and no
model has been called.

## Run it

```bash
make db-up    # a throwaway postgres:16 on 127.0.0.1:55440, for the tests
make check    # lint, types, tests and fitness functions, migrations, secrets
```

`uv` is the only thing to install first: `make check` runs `uv sync`'s
environment. Squawk, gitleaks and Lighthouse CI are skipped with a note if
they aren't installed locally; CI installs them and fails instead.

The tests load the dictionary from OpenJLPT's pinned build (commit
`bf4e1ee`), expected in `data/raw/openjlpt-bf4e1ee/` (git-ignored):

```bash
uv run juku-data fetch-dictionary
```

The first run also builds a synthetic database of 5,000 learners for the
query-plan checks (about 3 minutes); it's kept on the test server until
the schema or the engine's write side changes.

The app itself, `juku serve`, needs the managed database (set up once
with `ops/db/setup.sh`, ADR-016), Juku's MCP server and the secrets in
`ops/compose.yaml`; it runs there, not on a laptop. Its pages can be
looked at without any of that, rendered with sample data:

```bash
uv run juku render-previews --out build/previews
```

## Layout

| Folder | What it does |
|---|---|
| `packages/juku-common/` | What every service shares: the rule file loader (`guardrails.yaml`), the hash-chained audit log, and the delegation tokens (signer and verifier) |
| `packages/juku-data/` | The dictionary load (`juku-data`), learner state and the learning engine (`juku_data.engine`): progress, Susumu the recommender, quizzes, reading practice, the plan |
| `packages/juku-mcp/` | Juku's MCP server (`juku-mcp serve`): the learner's data, read-only, scoped by the delegation token in each call's `_meta`; `attacks/` holds the SAF1 attack suite and its committed prediction |
| `packages/juku-ops/` | The jobs cron runs (`juku-ops`): the audit-log importer, the heartbeat, partition upkeep, the nightly state check |
| `app/` | The web app (`juku serve`): FastAPI pages in Indonesian (Jinja2, Babel), consent and invite codes, the budget guard, Shiori's chat (PydanticAI) and its citation check, export and deletion; and the weekly pipeline (`juku run-weekly --due`, `app/src/juku_app/pipeline/`) with the Run Inspector |
| `app/web/` | The two Vue islands, chat and quiz (Vite, Vitest), with FE7's size budget and FF12's Lighthouse config |
| `packages/juku-testkit/` | Test helpers: the fitness-function and guardrail (G1) harnesses, both pytest plugins, and throwaway databases |
| `evals/` | Agent evals and their fixture learners: `memory/` holds MEM1's 15 tasks (agent-eval-harness's format), `pipeline/` the weekly pipeline's 10 learners and the planted bad outputs `load/` holds the load test (FF10): `run.py`, Locust and `results.md`. |
| `migrations/` | Alembic for the `app` database, one branch per owner (`monitoring`, `data`, `app`) |
| `guardrails.yaml` | Every limit Juku enforces, in one reviewed file, including the fitness functions' status and thresholds |
| `ops/` | Deployment: `compose.yaml`, the managed database's roles and set-up script, the crontab, Grafana's dashboards and alerts, and the gateway's routes for Juku |
| `docs/planning/` | Specs and plans: phase 1–2, slice plan, scale path, standard checks, spike write-ups |
| `docs/adr/` | Architecture decisions (ADR-001 to ADR-027) and their index |

A request's path through the code, the glossary and "where to change
things" are in [the guide](docs/guide.md).

## Docs

- **[Planning](docs/planning/README.md):** every spec and plan (the phase
  docs, the slice plan and cost model, the scale path, the standard checks)
  and the six week-0 spike write-ups with their measured results.
- **[Architecture decisions](docs/adr/README.md):** an index of ADR-001 to
  ADR-027, each with its options considered, plus the reuse map.
- **[The guide](docs/guide.md):** how one request flows through the code,
  a glossary, and where to change things.
- **[JOURNEY](JOURNEY.md):** what broke, what was wrong, and what changed.
