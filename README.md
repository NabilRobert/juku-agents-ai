# Juku

塾 (*juku*): a Japanese cram school, where staff coach students towards an
exam.

An agentic learning platform for Indonesian adults studying for the JLPT,
levels N5 to N2. Its staff is a small crew of agents:
- **Shiori**, the lead: the one learners talk to, and the keeper of their memory;
- **Hana:** plans each week;
- **Kenta:** writes the reports;
- **Rin:** the critic.

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

All knowledge of Japanese comes from open dictionaries (JMdict, KANJIDIC2,
Tatoeba), reached only through MCP tools.

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

**Status: planning.** No app code yet. Building starts after the
prerequisites in the [slice plan](docs/planning/slice-plan.md) are met.

## Planning docs

- [Phase 1: problem, users and success metrics](docs/planning/phase-1-problem-brief.md)
- [Phase 2: requirements, constraints and privacy](docs/planning/phase-2-requirements-constraints.md)
- [Phase 5: architecture decisions](docs/planning/phase-5-architecture-decisions.md)
- [Slice plan and cost model](docs/planning/slice-plan.md)
