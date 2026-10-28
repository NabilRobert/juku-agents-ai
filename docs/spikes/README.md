# Week-0 spikes: results

The six spikes from the [slice plan](../planning/slice-plan.md#spikes-local-0),
run on 2026-10-28, locally and at $0:
- no model calls and no API keys;
- no server touched;
- downloads only with Arthur's OK.

Each spike's code, raw output and full write-up is on its own branch, in
`spikes/<n>-<topic>/`.

| # | Question | Result | Pass rule | Branch |
|---|---|---|---|---|
| 1 | How big is the dictionary, and how long does it load? | **299 MB**, loaded in **18 s**; a fresh repeat load is identical, table by table (md5) | Under 1 GB, repeatable: **pass** | `spike/dictionary-load` |
| 2 | Do the recommender and i+1 queries fit? | Worst call **120 ms** at 0/100/500 known words, N5–N2, through an MCP server, after one fix (v1 spent ~300 ms in JIT) | Under 200 ms each: **pass** | `spike/recommender-query` |
| 3 | Does Grafana fit? | Idle **217 MiB** median uncapped; **244–251 MiB** in a 256 MB cap; `GOMEMLIMIT` doesn't help | Well under 256 MB: **fail**, so cron alerts | `spike/grafana-memory` |
| 4 | How cleanly do the JLPT lists and Tatoeba map to JMdict? | **98.0%** of JLPT rows unique; 24 ambiguous and 15 unmatched after the rules. **95.2%** of Tatoeba tokens map; **97.1%** of indexed sentences map fully, with a 10-word override list | Counted, rules written: **pass** | `spike/jlpt-mapping` |
| 5 | Does Sumopod report cached input tokens? | **Yes**, in all 6,792 raw responses; **32%** of prompt tokens were cached, automatically | Answered: **pass** (cost-model edit proposed below) | `spike/cached-tokens` |
| 6 | Does the delegation chain hold through the gateway? | The gateway's `main` **drops `_meta`**. With a 6-line patch to a local copy: token unchanged, **15/15 attacks refused and logged**, 3/3 legitimate calls pass | `_meta` unchanged, every attempt fails and is logged: **fail as the gateway stands; pass with the patch** | `spike/delegation-chain` |

Time: every spike finished inside its time box.

## 1. Dictionary load

- **Data** (fetched 2026-10-28, all checksums committed):
  - JMdict_e 2026-10-28, KANJIDIC2 2026-301 and KRADFILE (EDRDG, CC BY-SA
    4.0);
  - Tatoeba export of 2026-10-24: Japanese and Indonesian sentences,
    jpn–ind links and the word index (CC BY 2.0 FR).
- **Done:** a standard-library parser to COPY files, then `postgres:16`,
  keys and indexes after the load. `test_parse.py` is mutation-checked.
- **Numbers:**
  - 218,971 entries; 443,930 glosses; 13,108 kanji;
  - 277,297 sentences; 1,178,440 index tokens;
  - 299 MB database (the data directory is 576 MB, 257 MB of it WAL from
    the load);
  - parse 9.5 s, COPY 3.3 s, indexes 5.3 s.
  - Row counts equal the source's element counts.
- **Found:**
  - JMdict declares the entity `ik` twice;
  - 105 duplicate index lines, and 214 index lines for deleted sentences;
  - JMdict IDs written into some index tokens (`前(#1392580)`).
- **Changes:** the scale path's "about 1 GB" for the dictionary can read
  "about 0.3 GB, measured".

## 2. Recommender and i+1 timing

- **Done:**
  - ADR-010's tables (`word_level`, `word_kanji`, `kanji_level`,
    `kanji_leverage`), built in 5 s;
  - `recommend_words` and `find_reading_sentences` in a minimal MCP server
    (mcp 2.3.0);
  - known words read from an `app` database holding 5,000 synthetic
    learners (2.1 M rows);
  - 50 timed calls per cell, at the MCP client.
- **Numbers, round trip p50 / max:** recommender 4–21 ms / 69 ms; reading
  query 3–72 ms / 120 ms.
  - The first recommender failed (220 ms p50, 722 ms max). Postgres JIT
    compiled a query whose repeated subplan inflated its cost estimate.
  - Beyond the rule: the reading query reaches 208 ms p95 at 2,000 known
    words; the recommender stays under 45 ms at 4,000.

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

## 4. JLPT and Tatoeba mapping

- **Data:** Waller's N5–N1 lists (CC BY), as republished by
  stephenmk/yomitan-jlpt-vocab at `b062d4e` (CC BY-SA 4.0), whose hand-added
  JMdict IDs served as a reference. tanos.co.uk didn't respond. N1 is
  included, as Arthur asked.
- **Rules:** match by spelling and reading. Then, in order:
  1. R1, priority tags;
  2. R2, primary form;
  3. R3, kana-word preference.

  Anything still tied is reported, never guessed.
- **Numbers:**
  - JLPT: 8,126 of 8,293 rows unique. R1–R3 settle 128, leaving 24
    ambiguous and 15 unmatched. For N5–N2: 4,866 rows, 14 ambiguous and 1
    unmatched (a typo, 田ぼ).
  - 99.7% agree with the reference. By hand, most of the 23 disagreements
    are the reference's errors (stale IDs, wrong homographs).
  - Tatoeba: 59.6% of Japanese sentences are indexed, and 69.1% of those
    map fully. の alone is 95% of the ambiguous tokens.
  - Hand check of 30 rule-decided tokens: 27 of 28 distinct keys right,
    1 doubtful.

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
  - ES256 tokens shaped on RFC 8693, single-use per call; a delegated
    token carries its parent, so narrowing is provable;
  - a Juku MCP server whose tools take no arguments;
  - 22 unit tests, with 20/20 mutants killed;
  - 18 attempts run directly, through a copy of the gateway's `main`, and
    through a patched copy.
- **Numbers:** see the table above. Directly, the three key-bound attacks
  succeed, which shows Juku's server must be reachable only through the
  gateway. Through the patched gateway, all are refused and logged, and
  both audit chains verify.

## Proposed changes to the planning docs

Not edited yet. Each needs Arthur's OK.

1. **Monitoring: cron alerts, not Grafana (spike 3)**, as ADR-009 and
   settled decision 3 already say. The same `monitoring` schema; a cron
   job runs the alert queries and sends to the Telegram bot. That frees
   about 250 MB on the server. Raising Grafana's cap to about 384 MB is
   the alternative, a server-budget call, and isn't recommended.
2. **A new prerequisite in the slice plan (spike 6): the gateway forwards
   `_meta` and stamps the caller**, as in
   `spikes/6-delegation-chain/gateway-meta-passthrough.patch`, with a test
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
   - per-call, single-use tokens;
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
6. **ADR-010 and LE4 (spike 2):**
   - `jit = off` on the Juku MCP server's role;
   - a fitness check that fails if a tool query's plan cost explodes or
     JIT kicks in;
   - words with no new kanji rank as leverage 0 (to confirm);
   - function words count as known in reading practice;
   - LE4 uses a per-learner incremental "unknowns per sentence", or a
     lookup by target word, rather than a scan, because the scan crosses
     200 ms near 2,000 known words.
7. **Slice 1 (spike 4):** adopt R1–R3 as written, plus R4 (Waller's gloss)
   and a reviewed override file for the top function words. Drop N1's
   single-kanji rows from the word levels. Treat the hand-added IDs as a
   second opinion that flags disagreements, not as ground truth.
8. **The scale path (spike 1):** the dictionary is about 0.3 GB, measured.

## Merge order

1. `docs/planning` into `main` (main has no planning docs yet).
2. The six `spike/*` branches, in any order. Each is cut from
   `docs/planning` and adds only its own `spikes/<n>-<topic>/` folder, so
   they don't conflict. Spike 2's and spike 4's scripts need spike 1's
   database at run time, not its code.
3. `docs/spikes` (this file) last, since it points into the spike
   folders.

## Licences recorded

| Data | Licence |
|---|---|
| JMdict, KANJIDIC2, KRADFILE | EDRDG, CC BY-SA 4.0 |
| Tatoeba sentences, links, index | CC BY 2.0 FR |
| JLPT lists | Jonathan Waller (tanos.co.uk), CC BY; republished with JMdict IDs by stephenmk/yomitan-jlpt-vocab, CC BY-SA 4.0 |
| Grafana OSS (image only, not shipped) | AGPL-3.0 |

The downloads are in `data/raw/` (git-ignored) and are never committed.
