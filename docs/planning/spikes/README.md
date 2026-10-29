# Week-0 spikes: results

The six spikes from the [slice plan](../slice-plan.md#spikes-local-0),
run on 2026-10-28, locally and at $0:
- no model calls and no API keys;
- no server touched;
- downloads only with Arthur's OK.

Each spike's code, raw output and full write-up is on its own branch, in
`spikes/<n>-<topic>/`.

**Plan change, the same day:** Juku's data became OpenJLPT (ADR-003, after
Arthur's "reuse before building" rule), so spikes 1, 2 and 4 were rerun on
it. The first results stay as the fallback, for a full JMdict import.

| # | Question | Result | Pass rule | Branch |
|---|---|---|---|---|
| 1 | How big is the dictionary, and how long does it load? | **OpenJLPT: 19 MB, 2 s**, identical on a repeat. Pinned to commit `bf4e1ee`: no release has this data. (Fallback, JMdict + KANJIDIC2 + Tatoeba: 299 MB, 18 s) | Under 1 GB, repeatable: **pass** | `spike/dictionary-load` |
| 2 | Do the recommender and i+1 queries fit? | **OpenJLPT, quieter rerun (load ~5): worst call 102 ms** (jit off) at 0/100/500 known words. Beyond the rule, the recommender reaches a p95 of 231 ms and a max of 649 ms at 4,000 known words; the reading query stays flat. (Fallback: worst 120 ms, after a JIT fix) | Under 200 ms each: **pass**; slice 2 makes the recommender incremental | `spike/recommender-query` |
| 3 | Does Grafana fit? | Idle **217 MiB** median uncapped; **244–251 MiB** in a 256 MB cap; `GOMEMLIMIT` doesn't help | Well under 256 MB: **fail**, so cron alerts | `spike/grafana-memory` |
| 4 | How complete is OpenJLPT for Juku? (was: how cleanly do the lists map) | **11 of 7,811 words unlinked**; all links resolve; 7.2% have no example; **90.7% of example tokens map to one word**, so 63.3% of sentences (66.1% with ない as grammar) qualify for i+1. Common words in neither list (父, 母, 顔) need a supplement. (Without OpenJLPT: 98.0% of rows unique, 24 ambiguous) | Counted, rules written: **pass** | `spike/jlpt-mapping` |
| 5 | Does Sumopod report cached input tokens? | **Yes**, in all 6,792 raw responses; **32%** of prompt tokens were cached, automatically | Answered: **pass** (cost-model edit proposed below) | `spike/cached-tokens` |
| 6 | Does the delegation chain hold through the gateway? | The gateway's `main` **drops `_meta`**. With a 6-line patch to a local copy: token unchanged, **15/15 attacks refused and logged**, 3/3 legitimate calls pass. **A PydanticAI agent ($0, TestModel/FunctionModel) sets the token per call via `process_tool_call`**, and it arrives unchanged | `_meta` unchanged, every attempt fails and is logged: **fail as the gateway stands; pass with the patch** | `spike/delegation-chain` |

**Time:** every spike finished inside its time box except spike 2. With its OpenJLPT rerun and the reruns under load, it took about 1.5 h against a 1 h box.

## 1. Dictionary load

- **OpenJLPT (the plan):** `data/openjlpt.sqlite` from evanclan/OpenJLPT
  (CC BY-SA 4.0), loaded into `postgres:16`.
  - 7,811 words, 13,718 examples, 2,383 kanji and 526 grammar points.
  - 19 MB database; loads in 2.0–2.3 s; two loads have identical md5s.
  - **Its latest release, v0.2.0, is an older, thinner dataset:** 8,334
    words with no JMdict IDs, and 100 grammar points. The data Juku plans
    on exists only on `main`, so it's pinned to commit `bf4e1ee`
    (2026-09-30) with a checksum. PyPI's `openjlpt` is 0.1.0.
  - The loader is plain spike code; pgloader is the off-the-shelf choice
    for slice 1.
- **The fallback** (JMdict_e 2026-10-28, KANJIDIC2 2026-301, KRADFILE, and
  the Tatoeba export of 2026-10-24):
  - 299 MB, loaded in 18 s, identical on a fresh repeat;
  - a mutation-checked parser;
  - data quirks recorded: a duplicate DTD entity, 105 duplicate and 214
    orphaned index lines, and JMdict IDs inside index tokens.

## 2. Recommender and i+1 timing

- **OpenJLPT (the plan):** ADR-010's rewritten tables and ordering (gaps,
  leverage, commonness from the rarest kanji's frequency, stable ID). The
  reading index covers 8,339 SudachiPy-tokenized example sentences. Both
  tools run through a minimal MCP server, with known words from an `app`
  database of 5,000 synthetic learners.
  - **Quieter rerun (load average about 5):** worst call 102 ms (jit off)
    and 123 ms (jit on). An earlier run gave 62 and 91 ms; under a load of
    13–21, single N2 calls reached 242–274 ms.
  - **At 4,000 known words** (an advanced N2 learner), `recommend_words`
    reaches a p95 of 231 ms and a max of 649 ms. The reading query stays
    flat (24 ms p50).
- **The fallback (JMdict and Tatoeba):** the worst call was 120 ms, after
  rewriting the recommender. The first version spent about 300 ms in JIT
  compilation. Its reading query over 102,568 sentences crossed 200 ms at
  about 2,000 known words.

## 3. Grafana memory

- **Done:**
  - `grafana/grafana:13.2.4` with a provisioned Postgres data source (on a
    read-only role) and a two-panel dashboard, on an internal network with
    no internet;
  - 5 minutes idle, 20 dashboard loads, then 2 more minutes idle, sampled
    every 10 s.
- **Numbers (MiB, median / max):**
  - uncapped: 217 / 249;
  - in a 256 MB cap: 244 / 251 (no OOM, but no headroom);
  - with `GOMEMLIMIT=150MiB`: 232 / 243. The live heap alone is over
    200 MiB.

## 4. How complete is OpenJLPT?

- **Links:**
  - 7,800 of 7,811 words carry a JMdict ID, and all resolve in JMdict
    2026-10-28. The 11 without one are phrases and rare spellings.
  - Where OpenJLPT and this spike's own rule-based mapping of Waller's
    lists cover the same (spelling, reading), 99.9% of IDs agree.
- **Examples:** 566 words (7.2%) have none, 400 of them at N1.
- **i+1:** SudachiPy (split mode C, with mode A for compounds) on 12,615
  distinct sentences:
  - 90.7% of the content tokens map to one word ID, 1.2% to several, and
    8.1% to none;
  - 63.3% of sentences map completely (66.1% with ない counted as
    grammar);
  - hand check: 29 of 30 sampled tokens right, 1 doubtful.
- **Gap:** common words that are **in neither Waller's lists nor
  OpenJLPT** (父, 母, 顔, 多く, 人々, 夕食).
- **Without OpenJLPT,** mapping Waller's lists and Tatoeba's index
  ourselves: 98.0% of rows unique, 24 ambiguous and 15 unmatched after
  three rules, and 97.1% of indexed sentences mapped with a 10-word
  override list. The hand-added reference IDs turned out stale or wrong in
  most disagreements.

## 5. Cached tokens

- **Done:** read 20 runs' `inspect.eval` logs in agent-eval-harness. No
  calls.
- **Numbers:** `prompt_tokens_details.cached_tokens` is present in every
  raw response. 3.06 M of 9.68 M prompt tokens were cached: 45–61% on the
  filesystem suites, 6–14% on Pagila.
- **Side finding for the harness:** its cost leaves cached tokens out (it
  uses Inspect's uncached `input_tokens`), so it errs **low** by about
  1.5%, not high as its note says.
  - $4.45 recorded, against $4.52 at the cache price.
  - The $0.534 Pagila basis becomes $0.537.

## 6. Delegation chain

- **Spec read first:** MCP **2026-07-28** (the July revision).
  - It makes MCP **stateless**: there is no `initialize`, no
    `Mcp-Session-Id`, and every request carries its context in `_meta`.
  - Custom `_meta` keys take a reverse-DNS prefix.
  - Audience validation is a MUST, and token passthrough is forbidden.
  - It still says nothing about delegation chains.
- **Done:**
  - Ed25519 tokens (PyJWT `EdDSA`) shaped on RFC 8693, single-use per
    call; a delegated
    token carries its parent, so narrowing is provable;
  - a Juku MCP server whose tools take no arguments;
  - 22 unit tests, with 20/20 mutants killed;
  - 18 attempts run directly, through a copy of the gateway's `main`, and
    through a patched copy.
- **PydanticAI (ADR-025):**
  - an `Agent` with `MCPToolset` (Streamable HTTP, the agent's gateway key)
    and a `process_tool_call` hook that mints each call's token and passes
    it as `metadata`, which PydanticAI sends as `_meta`;
  - through the patched gateway: 3 of 3 calls allowed, with the token and
    `traceparent` unchanged (Shiori on `TestModel`, Keiko delegated on
    `FunctionModel`);
  - through `main`: refused, because the token is dropped.

  No hand-written loop is needed. The packages came from the local uv
  cache, with no download: pydantic-ai-slim[mcp] 2.56.0, fastmcp-slim
  4.1.4, mcp 2.3.0, PyJWT 2.15.1 and cryptography 50.0.2.
- **Numbers:** see the table above. Directly, the three key-bound attacks
  succeed, which shows Juku's server must be reachable only through the
  gateway. Through the patched gateway, all are refused and logged, and
  both audit chains verify.

## Proposed changes to the planning docs

**Status (2026-10-28):**
- Applied on `docs/planning` in a630926, by the planning session, with
  Arthur's decisions.
- One difference from the proposals below: **monitoring stays on Grafana,
  capped at 384 MB** (Arthur), not cron alerts, after a check of the
  server's memory.
- Spike 2's later finding (231 ms p95 at 4,000 known words) turned item 6's
  "precompute if needed" into a decision. That's on
  `docs/recommender-incremental` (0010ed2), cut from `docs/planning`, to
  merge into it.

The proposals as written:

1. **Monitoring: cron alerts, not Grafana (spike 3)**, as ADR-009 and
   settled decision 3 already say. The same `monitoring` schema; a cron
   job runs the alert queries and sends to the Telegram bot. That frees
   about 250 MB on the server. Raising Grafana's cap to about 384 MB is
   the alternative, a server-budget call, and isn't recommended.
2. **A new prerequisite in the slice plan (spike 6): the gateway forwards
   `_meta` and stamps the caller**, as in
   `spikes/6-delegation-chain/gateway-meta-passthrough.patch` (on branch spike/delegation-chain; since merged upstream as NabilRobert/mcp-security-gateway#6), with a test
   that a client-sent caller is overwritten. It's gateway-repo work for
   Arthur, needed before slice 3 runs through the gateway, not only before
   launch (settled decision 4). Also minor: `mcp_gateway/cli.py` lacks a
   `__main__` guard.
3. **ADR-006:**
   - "the MCP session is opened with it" becomes "every MCP request
     carries it in `_meta`", since MCP 2026-07-28 has no sessions;
   - the server reads two databases (app and dictionary) in two queries;
   - Juku's server has no published port.
4. **ADR-018:** fix the details spike 6 settled:
   - the key `io.github.nabilrobert.juku/delegation`;
   - per-call, single-use Ed25519 tokens, minted in PydanticAI's
     `process_tool_call`;
   - the parent token embedded in a delegated one;
   - the gateway's caller stamp as the actor binding;
   - the reading of "no token passthrough" (an audience-bound token the
     gateway neither uses nor validates).

   Phase 2 ID-R2's "the gateway passes through unchanged" becomes "must
   forward; its `main` drops it".
5. **The cost model (spike 5's pass rule asks for this).** In "Levers if
   spend runs high", item 2 becomes:

   > Prompt caching is automatic on Sumopod: 32% of the harness's prompt
   > tokens were served cached (45–61% on multi-call suites), reported in
   > `prompt_tokens_details.cached_tokens` (spike 5). Keep the static parts
   > of each prompt first so it applies. Whether they are billed at the
   > table's $0.025/M is checked on Sumopod's billing page in slice 7.

   The planning figures ($0.005 a question, $0.015 a report) stay as they
   are: they assume no caching, so they err high. The measured basis note
   gains: "the harness's cost omits cached tokens (about −1.5%); $0.537
   with them".
6. **ADR-010 (spike 2):**
   - `jit = off` on the Juku MCP server's role;
   - a fitness check that fails if a tool query's plan cost explodes or
     JIT kicks in;
   - keep each learner's recommender candidates incrementally (unknown
     words with at most one unknown kanji), updated as words become known.
     FF1 times `recommend_words` at 4,000 known words;
   - The reading query is fine on OpenJLPT.
7. **ADR-003 (spikes 1 and 4):**
   - record that the OpenJLPT data Juku uses has **no release**, so it's
     pinned to commit `bf4e1ee` with a checksum. v0.2.0 is the older
     dataset, and PyPI is at 0.1.0;
   - add a small, reviewed **supplement file** of common words outside
     the JLPT lists (父, 母, 顔…), with JMdict IDs, so i+1 sentences can
     use them;
   - count ない and OpenJLPT's grammar patterns as grammar in LE4, with
     function words, names and numbers as known.
8. **The scale path (spike 1):** the dictionary is about 20 MB with
   OpenJLPT, or about 0.3 GB with a full JMdict import.

## Merge order

1. `docs/planning` into `main` (main has no planning docs yet).
2. The six `spike/*` branches, in any order. Each is cut from an earlier
   `docs/planning` (b34b8a4, before the OpenJLPT commits) and adds only its
   own `spikes/<n>-<topic>/` folder, so they don't conflict. Spike 2's and spike 4's scripts need spike 1's
   database at run time, not its code.
3. `docs/spikes` (this file, since moved to docs/planning/spikes/README.md) last, since it points into the spike
   folders.

## Licences recorded

| Data | Licence |
|---|---|
| JMdict, KANJIDIC2, KRADFILE | EDRDG, CC BY-SA 4.0 |
| Tatoeba sentences, links, index | CC BY 2.0 FR |
| OpenJLPT (commit bf4e1ee) | CC BY-SA 4.0; built from JMdict, KANJIDIC2 (EDRDG, CC BY-SA 4.0), Waller's lists (CC BY) and Tatoeba (CC BY 2.0 FR) |
| JLPT lists (fallback) | Jonathan Waller (tanos.co.uk), CC BY; republished with JMdict IDs by stephenmk/yomitan-jlpt-vocab, CC BY-SA 4.0 |
| SudachiPy 0.7.0, sudachidict-core 20260723.1 | Apache-2.0 |
| pydantic-ai-slim 2.56.0 (spike 6, from the uv cache) | MIT |
| Grafana OSS (image only, not shipped) | AGPL-3.0 |

The downloads are in `data/raw/` (git-ignored) and are never committed.
