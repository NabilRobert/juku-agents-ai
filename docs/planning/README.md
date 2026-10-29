# Planning docs

Every spec and plan for Juku, kept as written and organised here. Decisions
are in [docs/adr](../adr/README.md); how the built code fits together is in
[the guide](../guide.md).

## Specs

- [Phase 1: problem, users and success metrics](phase-1-problem-brief.md):
  who Juku is for, what it must show, and the targets it's measured on.
- [Phase 2: requirements, constraints and privacy](phase-2-requirements-constraints.md):
  must, should and could; consent, retention and deletion; guardrails.

## Plans

- [Slice plan and cost model](slice-plan.md): prerequisites, spikes,
  the slices in order, and the budget.
- [Scale path](scale-path.md): built for ten, designed for thousands; the
  data design and the fitness functions.
- [Standard checks](standard-checks.md): the checks at every step, and
  before paid runs, server steps and publishing.

## Spikes (week 0, $0)

- [Summary of all six spikes](spikes/README.md): questions, results, pass
  or fail, and the plan changes they led to.
- [1. Dictionary load](spikes/1-dictionary-load.md)
- [2. Recommender and i+1 query timing](spikes/2-recommender-query.md)
- [3. Grafana's memory](spikes/3-grafana-memory.md)
- [4. How complete OpenJLPT is](spikes/4-jlpt-mapping.md)
- [5. Cached tokens on Sumopod](spikes/5-cached-tokens.md)
- [6. The delegation chain through the gateway](spikes/6-delegation-chain.md)

Each spike's measured results sit beside its write-up, in
`spikes/<n>-<topic>/results/`. The spike code lives on its `spike/*` branch.
