# SAF1: the attack suite on Juku's own surfaces

Fifteen attacks (ADR-020, Phase 2 SAF-R1), each with its outcome
**predicted in [prediction.yaml](prediction.yaml) and committed before the
first run**, then run two ways at $0 (SAF-R2):
- **direct:** Juku's MCP server alone, as it would have to run with no
  gateway in front, so an attacker who reaches it writes their own caller
  stamp;
- **gateway:** through mcp-security-gateway at 66227a2, which includes
  P6 (it forwards `_meta` and stamps the caller; merged as d89f20b). Each
  agent has its own key and allow-list.

Three attacks are carried out by a scripted "gullible" agent (PydanticAI's
`FunctionModel`) that obeys any instruction it reads in a tool result; the
instructions are planted in a fixture copy of the Tatoeba sentences, never
in the dictionary other tests or learners use. Its tokens are minted
honestly, one per call, in PydanticAI's `process_tool_call` hook. The rest
are an attacker's raw MCP calls with crafted tokens, arguments and `_meta`.
No model is called.

```bash
make db-up
GATEWAY_REF=66227a2 packages/juku-mcp/attacks/run_through_gateway.sh   # both ways; writes results-*.json and logs/
uv run pytest packages/juku-mcp/tests/test_attack_suite.py   # direct only, in make check
```

## Results (2026-10-28)

**15 of 15 as predicted, both ways.** All three audit chains verify. The
first gateway run used spike 6's patch on c5e50ac; the rerun on the
merged P6 (66227a2) gave the same outcomes. In its audit log, all 23
calls carry `_meta`, and the one forged caller claim (Keiko's key with
Shiori's token) is marked as overwritten.

| Attack | Direct | Through the gateway |
|---|---|---|
| Injection: read another learner by ID | refused: unexpected arguments | refused: unexpected arguments |
| Injection: save a note about the learner's health | no effect (no such tool) | no effect |
| Injection: request a new plan five times | one queued, the rest capped | one queued, the rest capped |
| A learner ID in the arguments | refused: unexpected arguments | refused: unexpected arguments |
| A token for B from the attacker's key | refused: bad signature | refused: bad signature |
| A's token with its learner edited | refused: bad signature | refused: bad signature |
| Keiko's hop switches to learner B | refused: learner changed | refused: learner changed |
| Keiko's hop adds a tool | refused: widened | refused: widened |
| Keiko's hop outlives its parent | refused: outlived parent | refused: outlived parent |
| A chain three agents deep | refused: too deep | refused: too deep |
| A token used twice | refused: replayed | refused: replayed |
| A token for MCP-backbone | refused: wrong audience | refused: wrong audience |
| **Keiko's key carrying Shiori's token** | **succeeds** (predicted) | refused: actor mismatch |
| **Keiko's key, Shiori's token, a forged caller stamp** | **succeeds** (predicted) | refused: actor mismatch (the gateway overwrites the stamp) |
| Keiko calls request_replan | refused: out of scope | blocked by the gateway's allow-list |

What it shows:
- **The two that succeed directly are why Juku's server has no published
  port** and shares no network with the app (ops/compose.yaml): without
  the gateway, nothing binds a chain to the key that made the call. Spike
  6 found the same; slice 8 must check the port on the server.
- **A gateway finding: its rules detector flagged none of the three
  results with planted instructions.** The gateway ran its rules layer
  only (detector `rules-251a56f28c31`; the model layer was off). Of the 22
  results it scanned, 3 were `find_reading_sentences` outputs carrying the
  planted text; the other 19 (14 `get_progress`, 5 `request_replan`) had
  none, so "0 of 22 flagged" overstates it. The planted lines don't use
  the phrases the rules look for. The gullible agent obeyed them, and
  Juku's server refused the call, because no tool takes a learner and the
  replan tool is capped; the defence here doesn't depend on the detector.
  For re-scoring with the model layer, `SAF1_CAPTURE=<file>` records each
  result's text exactly as the gateway scanned it.
- Unlike spike 6's server, Keiko calling a tool outside her list is refused
  even directly: the server checks each token's tools against the agent's
  list in guardrails.yaml, not only against the token.

The real-model run (once, about $0.12) waits for slice 7 and Arthur's OK.
