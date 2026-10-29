# Architecture decisions

Juku's decisions live in one file, [phase-5-architecture-decisions.md](phase-5-architecture-decisions.md),
which also holds the reuse map and the decisions settled with Arthur. Each ADR
there gives the decision, why, and the options considered. This page is the index.

| ADR | Decision | Status |
|---|---|---|
| [ADR-001](phase-5-architecture-decisions.md#adr-001-the-users-are-indonesian-jlpt-learners-in-a-study-group-settled) | The users are Indonesian JLPT learners in a study group | settled |
| [ADR-002](phase-5-architecture-decisions.md#adr-002-pitstops-pattern-applied-to-learning-settled) | Pitstop's pattern, applied to learning | settled |
| [ADR-003](phase-5-architecture-decisions.md#adr-003-openjlpt-as-the-data-in-postgres-served-by-mcp-backbone-settled-revised-2026-10-28) | OpenJLPT as the data, in Postgres, served by MCP-backbone | settled; revised 2026-10-28 |
| [ADR-004](phase-5-architecture-decisions.md#adr-004-a-web-page-first-whatsapp-later-settled) | A web page first, WhatsApp later | settled |
| [ADR-005](phase-5-architecture-decisions.md#adr-005-a-thin-python-app-with-pydanticai-for-the-agents-revised-2026-10-28) | A thin Python app, with PydanticAI for the agents | revised 2026-10-28 |
| [ADR-006](phase-5-architecture-decisions.md#adr-006-jukus-own-mcp-server-scoped-by-session-read-only) | Juku's own MCP server, scoped by session, read-only | accepted |
| [ADR-007](phase-5-architecture-decisions.md#adr-007-four-agents-with-the-critics-checks-repeated-in-code) | Four agents, with the critic's checks repeated in code | accepted |
| [ADR-008](phase-5-architecture-decisions.md#adr-008-memory-is-structured-inspectable-and-evidence-backed-settled) | Memory is structured, inspectable and evidence-backed | settled |
| [ADR-009](phase-5-architecture-decisions.md#adr-009-monitoring-is-grafana-over-postgres-with-alerts) | Monitoring is Grafana over Postgres, with alerts | accepted |
| [ADR-010](phase-5-architecture-decisions.md#adr-010-the-learning-engine-is-deterministic-code) | The learning engine is deterministic code | accepted |
| [ADR-011](phase-5-architecture-decisions.md#adr-011-gpt-5-mini-through-sumopod) | gpt-5-mini through Sumopod | accepted |
| [ADR-012](phase-5-architecture-decisions.md#adr-012-spend-is-capped-in-three-layers-in-two-pools) | Spend is capped in three layers, in two pools | accepted |
| [ADR-013](phase-5-architecture-decisions.md#adr-013-invite-codes-and-nicknames-no-email) | Invite codes and nicknames, no email | accepted |
| [ADR-014](phase-5-architecture-decisions.md#adr-014-scheduling-is-external-cron-with-a-dead-mans-switch) | Scheduling is external cron, with a dead-man's switch | accepted |
| [ADR-015](phase-5-architecture-decisions.md#adr-015-evaluation-driven-development-tasks-first-then-a-closed-loop) | Evaluation-driven development: tasks first, then a closed loop | accepted |
| [ADR-016](phase-5-architecture-decisions.md#adr-016-hosting-is-docker-compose-on-the-shared-server-with-a-managed-database) | Hosting is Docker Compose on the shared server, with a managed database | accepted |
| [ADR-017](phase-5-architecture-decisions.md#adr-017-a-fixed-window-and-results-reported-as-they-are-settled) | A fixed window, and results reported as they are | settled |
| [ADR-018](phase-5-architecture-decisions.md#adr-018-agent-identity-and-delegated-authorization-in-a-small-testable-form) | Agent identity and delegated authorization, in a small testable form | accepted |
| [ADR-019](phase-5-architecture-decisions.md#adr-019-guardrails-are-code-with-tests-in-one-rule-file) | Guardrails are code with tests, in one rule file | accepted |
| [ADR-020](phase-5-architecture-decisions.md#adr-020-a-safety-eval-on-jukus-own-attack-surfaces) | A safety eval on Juku's own attack surfaces | accepted |
| [ADR-021](phase-5-architecture-decisions.md#adr-021-memory-not-continual-learning-settled) | Memory, not continual learning | settled |
| [ADR-022](phase-5-architecture-decisions.md#adr-022-built-for-ten-designed-for-thousands) | Built for ten, designed for thousands | accepted |
| [ADR-023](phase-5-architecture-decisions.md#adr-023-anti-regression-by-fitness-functions-plus-the-harness-gate) | Anti-regression by fitness functions, plus the harness gate | accepted |
| [ADR-024](phase-5-architecture-decisions.md#adr-024-the-frontend-is-server-rendered-lazy-and-held-to-a-budget-revised-2026-10-28) | The frontend is server-rendered, lazy, and held to a budget | revised 2026-10-28 |
| [ADR-025](phase-5-architecture-decisions.md#adr-025-a-framework-for-every-component-the-folders-frameworks-over-plain-code-rule) | A framework for every component (the folder's "frameworks over plain code" rule) | accepted |
| [ADR-026](phase-5-architecture-decisions.md#adr-026-the-dictionarys-index-is-mirrored-into-the-app-database-the-load-is-python-over-copy-track-a-2026-10-28) | The dictionary's index is mirrored into the app database; the load is Python over COPY | accepted (built, 2026-10-28) |
| [ADR-027](phase-5-architecture-decisions.md#adr-027-what-building-jukus-mcp-server-settled-track-b-2026-10-28) | What building Juku's MCP server settled | accepted (built, 2026-10-28) |

Also in that file: [the reuse map](phase-5-architecture-decisions.md#reuse-map-the-folders-reuse-before-building-rule)
and [what was settled with Arthur](phase-5-architecture-decisions.md#settled-with-arthur-2026-10-27-go-with-your-recommendations-rush).
The specs and plans the decisions serve are indexed in [docs/planning](../planning/README.md).
