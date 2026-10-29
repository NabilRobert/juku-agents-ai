# Spike 6: does the delegation chain hold through the gateway?

**Fail as the gateway stands; pass with a 6-line gateway patch.**
- **mcp-gateway's `main` (414c755) drops `_meta`.** It forwards a call as
  `call_tool(name, arguments)`, so the delegation token never reaches
  Juku's server, and every call is refused, the legitimate ones included.
  (The SDK still carries `traceparent` across.)
- **With [gateway-meta-passthrough.patch](https://github.com/NabilRobert/juku-agents-ai/blob/spike/delegation-chain/spikes/6-delegation-chain/gateway-meta-passthrough.patch),
  applied to a local copy:** `_meta` arrives unchanged (the token's
  sha256 matches on every call that reached the server). All 15 attempts
  to break the chain fail, every one is logged, and the 3 legitimate
  calls pass.

The patch forwards `_meta` and stamps the authenticated caller. It is a
change for the gateway repo, Arthur's; nothing there was modified.

```
pytest -q                 # 22 tests of the token rules
python mutate.py          # disables each of 20 checks in turn: 20/20 killed
./run.sh <venv python> [<PydanticAI venv python>]   # the attack suite, plus the PydanticAI check
```

## 1. The MCP authorization spec, read first

The current revision is **2026-07-28** (released 2026-07-28; the July
revision Arthur noted). mcp 2.3.0, which the gateway and this spike use,
implements it. What matters for Juku:

- **MCP is now stateless.** The `initialize` handshake and
  `Mcp-Session-Id` are gone; every request carries its protocol version
  and capabilities in `_meta`. So there is no MCP session to open with a
  token, which is what ADR-006 says the app does. The token has to ride on
  each request. A token per call, single-use by `jti`, fits that exactly.
- **`_meta` keys:** custom keys take a reverse-DNS prefix; prefixes whose
  second label is `modelcontextprotocol` or `mcp` are reserved, and
  `traceparent`, `tracestate` and `baggage` are reserved for
  OpenTelemetry. Juku's key: `io.github.nabilrobert.juku/delegation`.
- **Authorization (HTTP, optional):**
  - OAuth 2.1 with RFC 8707 resource indicators;
  - servers MUST check that a token was issued for them (the audience);
  - **token passthrough is forbidden** ("MUST NOT accept or transit any
    other tokens");
  - the access token goes in `Authorization: Bearer` on every request.
- **Agent identity and delegation chains:** the spec says nothing (no
  `act`, no token exchange). It's still unsettled, so ADR-018's own design
  stands.
- **How Juku's token squares with "no passthrough":** the delegation
  token isn't an OAuth access token for anything the gateway talks to.
  - It is audience-bound to Juku's server (checked), and the gateway
    neither validates nor uses it.
  - Juku's server never sends it on.
  - So no token is ever reused at another audience, which is the rule's
    purpose. A strict reader could still say the gateway "transits" it.
  - The spec-native alternative would make it the `Authorization` token of
    Juku's server, which collides with the gateway's own agent keys in that
    header.
  - **Proposed:** keep `_meta`, write this reading into ADR-018, and
    revisit if MCP adds a delegation extension.

## 2. What was built

- `delegation.py`: the app's signer and the server's verifier.
  - Ed25519-signed JWTs (PyJWT, `EdDSA`) shaped on RFC 8693: `sub` is the pseudonymous learner;
    `act` is nested, outermost = the agent acting now; plus `purpose`,
    `run`, `tools`, `aud = juku-mcp`, a 60 s `exp` and a single-use `jti`.
  - A delegated token (Keiko, for Shiori's `request_replan`) carries its
    parent token. The server can then prove the hop only narrowed:
    - the tools are a subset;
    - the expiry is no later;
    - the learner is the same;
    - the chain is exactly one hop longer;
    - it's on the one allowed path (Keiko ← Shiori);
    - and the parent allowed `request_replan`.
  - More than 2 agent hops is refused.
  - With a gateway, the chain's current actor must equal the caller the
    gateway authenticated.
- `juku_server.py`: a low-level MCP server, with `get_progress`,
  `get_memory` and `request_replan`.
  - **No tool takes any argument;** the learner comes only from the
    verified token.
  - Every call is logged, allowed or refused, with its chain and a hash
    of the token, never the token itself.
- `attack.py` and `run.sh`: 3 legitimate calls and 15 attacks, run three
  ways.
  - Directly against the server.
  - Behind a copy of the gateway's `main`, exported with `git archive`
    and run unmodified.
  - Behind a copy with the patch, where the server requires the gateway's
    caller stamp.
  - Each Shiori and Keiko has its own gateway key and allow-list (Keiko's
    lacks `request_replan`).
  - All keys are test values made per run, and the gateway's audit chain
    verifies after each run.

## 3. Results

| Attempt | Direct | Gateway `main` | Gateway + patch |
|---|---|---|---|
| Shiori reads her learner's progress (legitimate) | allowed | **refused: no token** | allowed |
| Keiko, delegated by Shiori, reads progress (legitimate) | allowed | **refused: no token** | allowed |
| A token's first use (legitimate) | allowed | **refused: no token** | allowed |
| Another learner: a `learner_id` argument | refused | refused | refused (unexpected arguments) |
| Another learner: a token for B from another signer | refused | refused* | refused (bad signature) |
| Another learner: A's token, learner edited to B | refused | refused* | refused (bad signature) |
| Another learner: Keiko's hop switches to B | refused | refused* | refused (changed the learner) |
| Widened scope: a tool outside the token | refused | refused* | refused (not in scope) |
| Widened scope: Keiko's hop adds a tool | refused | refused* | refused (widened the tools) |
| Widened scope: Keiko's hop outlives its parent | refused | refused* | refused (extended the expiry) |
| Expired token | refused | refused* | refused (expired) |
| Replayed token | refused | refused* | refused (replayed) |
| Wrong audience (MCP-backbone's) | refused | refused* | refused (wrong audience) |
| A chain 3 agent hops deep | refused | refused* | refused (too deep) |
| **Keiko's key carrying Shiori's chain** | **allowed** | refused* | refused (actor ≠ calling key) |
| Keiko's key, Shiori's chain, a forged caller in `_meta` | **allowed** | refused* | refused (the gateway overwrites the caller) |
| Keiko calls a tool outside her allow-list | **allowed** | refused by the gateway | refused by the gateway |
| No token at all | refused | refused | refused |

\* Refused only because the token never arrived ("no delegation token"),
not by the check named.

| | Direct | Gateway `main` | Gateway + patch |
|---|---|---|---|
| Legitimate calls allowed | 3/3 | **0/3** | **3/3** |
| Attacks refused | 12/15 | 15/15 (for the wrong reason) | **15/15** |
| Attacks logged | 15/15 | 15/15 | **15/15** |
| Token arrived unchanged | 17/17 | **0/17** | **16/16** that reached the server |
| Our `traceparent` arrived unchanged | yes | yes | yes |

- **Direct** shows why the gateway matters. With no gateway, nothing can
  bind the chain to a key, and anyone who can reach the server can forge
  the caller. **Juku's MCP server must be reachable only through the
  gateway** (no published port), which slice 8 must check.
- **Logged:** every attempt has a line in Juku's log
  ([logs/](6-delegation-chain/results/logs/)), or in the gateway's audit log for the one it
  refuses itself.
  - The gateway's `result` line says `allowed` for calls Juku refused: its
    `decision` is the detector's verdict, with `is_error: true`.
  - The authorization verdict lives in Juku's log. That's the one the
    "who accessed my data" page and the refusal alert should read.
- **Unit level:** 22 tests, one per rule. `mutate.py` disables each of the
  20 checks in turn, and every mutant is killed
  ([results-mutation.txt](6-delegation-chain/results/results-mutation.txt)).

## 3a. Through PydanticAI (ADR-025)

**Pass with the patched gateway: PydanticAI can set `_meta` per call, with
no hand-written loop.**
- `pai_check.py` runs an `Agent` with PydanticAI's `MCPToolset`: Streamable
  HTTP to the gateway, with the agent's own key in the `Authorization`
  header.
- Its `process_tool_call` hook mints a fresh single-use token for each call
  and passes it as `call_tool(name, args, metadata={...})`. PydanticAI
  sends that as the request's `_meta`.
- The models are `TestModel` (Shiori, one `get_progress` call) and a
  `FunctionModel` (Keiko, delegated by Shiori, two calls), so it costs $0.

| | Gateway `main` | Gateway + patch |
|---|---|---|
| Shiori (`TestModel`), 1 call | refused: no delegation token | allowed; token and `traceparent` unchanged |
| Keiko (`FunctionModel`, delegated), 2 calls | refused: no delegation token | both allowed, each with its own token; unchanged |

The output is in `results-pydantic-ai-*.json`.

- **For slice 3,** `process_tool_call` is the hook where the app mints each
  call's token. The run's `deps` carry the learner, the chain and the
  allowed tools. With `tool_error_behavior="error"`, a refusal ends the
  run as a `ToolError`, rather than letting the model retry it.
- **Packages,** all installed from the local uv cache into the spike's own
  venv, nothing downloaded:
  - pydantic-ai-slim[mcp] 2.56.0 (MIT; the version Arthur's MCP-backbone
    checkouts pin), with fastmcp-slim 4.1.4 and mcp 2.3.0;
  - PyJWT 2.15.1 and cryptography 50.0.2.

  PyPI's latest is 2.63.0, released today; slice 3 picks the pin.

## 4. What it changes in the plan (proposed, not yet edited)

1. **Gateway repo, before slice 3 can run through it:** the `_meta`
   passthrough and the caller stamp, as in the patch, plus a test that a
   client-sent caller is overwritten.
   - Settled decision 4 already puts "the actor check" in the gateway
     before launch.
   - This makes it a prerequisite for Juku's MCP server behind the
     gateway, not only for launch.
   - The stamp is the simpler half: the gateway stays token-agnostic (no
     app public key), and the binding is checked where the other checks
     are.
2. **ADR-006:** "the MCP session is opened with it" becomes "every MCP
   request carries it in `_meta`". MCP 2026-07-28 has no sessions.
3. **ADR-018:** fix the details this spike settled:
   - the `_meta` key name;
   - per-call, single-use tokens, Ed25519-signed and minted in PydanticAI's
     `process_tool_call`;
   - the parent token embedded in a delegated one;
   - the caller stamp as the actor binding;
   - the reading of "no token passthrough" above;
   - Juku's server reachable only through the gateway.
4. **Phase 2, ID-R2:** "which the gateway passes through unchanged
   (spike 6 checks this)" becomes "which the gateway must forward; its
   `main` drops it (spike 6), so the patch is a prerequisite".
5. **Gateway follow-up (minor):** `mcp_gateway/cli.py` has no `__main__`
   guard, so `python -m mcp_gateway.cli serve` exits silently. The
   `mcp-gateway` script works.
