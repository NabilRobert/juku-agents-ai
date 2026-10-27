# JLPT study assistant (working name)

A small AI assistant for Indonesian learners preparing for the JLPT. It
answers questions about Japanese vocabulary, kanji and example sentences,
in Indonesian, from open dictionary data. Every fact it states comes from
a read-only database query and cites the entry it came from.

It is the seventh piece of a portfolio, and the first with real users. It
runs on the same stack as the others:
- [MCP-backbone](https://github.com/NabilRobert/MCP-backbone): the
  read-only database MCP server;
- [mcp-security-gateway](https://github.com/NabilRobert/mcp-security-gateway):
  in front of it;
- [agent-eval-harness](https://github.com/NabilRobert/agent-eval-harness):
  measures answer quality;
- agent-observability (Project 6): traces each request.

**Status: planning.** No app code yet. Building starts after the
prerequisites in the [slice plan](docs/planning/slice-plan.md) are met.

## Planning docs

- [Phase 1: problem, users and success metrics](docs/planning/phase-1-problem-brief.md)
- [Phase 2: requirements, constraints and privacy](docs/planning/phase-2-requirements-constraints.md)
- [Phase 5: architecture decisions](docs/planning/phase-5-architecture-decisions.md)
- [Slice plan and cost model](docs/planning/slice-plan.md)
