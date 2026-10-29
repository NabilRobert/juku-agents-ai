"""Spike 2 (OpenJLPT): the same timing as ../bench.py, on OpenJLPT's tables
and ADR-010's rewritten ordering: gaps from easier levels first, then the
unknown kanji's leverage, then commonness (the rarest kanji's KANJIDIC2
frequency rank), then OpenJLPT's stable ID.

Through an MCP server (MCPServer, in memory). Known words come from the app
database (learner_word_oj, 3 fixture learners plus 5,000 synthetic ones).

Usage: python bench.py <jit on|off> > results-jit-<on|off>.md
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from typing import Any

import asyncpg
from mcp import Client
from mcp.server.mcpserver import MCPServer

DSN = "postgresql://postgres@127.0.0.1:55437/{db}"
SIZES, LEVELS, WARMUP, RUNS = (0, 100, 500), (5, 4, 3, 2), 5, 50

RECOMMEND = """
WITH known_kanji AS (
    SELECT character AS kanji FROM ojlpt.kanji WHERE level > $2   -- every kanji of the easier levels
    UNION
    SELECT wk.kanji FROM ojlpt.word_kanji wk WHERE wk.id = ANY ($1::text[])),  -- and those in known words
cand AS (
    SELECT w.id, w.word, w.reading, w.level, w.commonness,
           count(wk.kanji) FILTER (WHERE kk.kanji IS NULL) AS n_new,
           min(wk.kanji) FILTER (WHERE kk.kanji IS NULL) AS new_k
    FROM ojlpt.word_level w
    LEFT JOIN ojlpt.word_kanji wk ON wk.id = w.id
    LEFT JOIN known_kanji kk ON kk.kanji = wk.kanji
    WHERE w.level >= $2 AND w.id <> ALL ($1::text[])
    GROUP BY w.id),
scored AS (
    SELECT c.*, coalesce(kl.words, 0) AS leverage
    FROM cand c LEFT JOIN ojlpt.kanji_leverage kl ON kl.kanji = c.new_k AND kl.level = $2
    WHERE c.n_new <= 1),
ranked AS (
    SELECT s.*, row_number() OVER (ORDER BY (level > $2) DESC, leverage DESC, commonness, id) AS rk FROM scored s),
varied AS (SELECT r.*, row_number() OVER (PARTITION BY new_k ORDER BY rk) AS nth FROM ranked r)
SELECT id, word, reading, level, new_k, leverage,
       CASE WHEN level > $2 THEN format('Kata N%s yang belum dikuasai. ', level) ELSE '' END
       || CASE WHEN new_k IS NULL THEN 'Tanpa kanji baru.'
               ELSE format('1 kanji baru: %s, muncul di %s kata N%s.', new_k, leverage, $2) END AS reason
FROM varied WHERE new_k IS NULL OR nth <= 3
ORDER BY rk LIMIT 10
"""

READING = """
WITH hits AS (
    SELECT sw.sentence_id, count(*) AS known_n FROM ojlpt.sentence_word sw
    WHERE sw.id = ANY ($1::text[]) GROUP BY sw.sentence_id),
one_unknown AS (
    SELECT ss.sentence_id FROM ojlpt.sentence_size ss JOIN hits h USING (sentence_id)
    WHERE ss.content_words - h.known_n = 1
    UNION ALL
    SELECT ss.sentence_id FROM ojlpt.sentence_size ss
    WHERE ss.content_words = 1 AND NOT EXISTS (SELECT 1 FROM hits h WHERE h.sentence_id = ss.sentence_id))
SELECT o.sentence_id, s.ja,
       (SELECT sw.id FROM ojlpt.sentence_word sw WHERE sw.sentence_id = o.sentence_id
          AND sw.id <> ALL ($1::text[]) LIMIT 1) AS new_word
FROM one_unknown o JOIN ojlpt.sentence_size s USING (sentence_id)
ORDER BY length(s.ja), o.sentence_id LIMIT 10
"""


def build(app: asyncpg.Pool, dic: asyncpg.Pool, learner: int) -> MCPServer:
    server = MCPServer("juku-spike2-openjlpt")

    async def known() -> tuple[list[str], float]:
        t = time.perf_counter()
        rows = await app.fetch("SELECT vocab_id FROM learner_word_oj WHERE learner_id = $1", learner)
        return [r[0] for r in rows], (time.perf_counter() - t) * 1000

    @server.tool()
    async def recommend_words(level: int) -> dict[str, Any]:
        """Ten words to learn next, with a reason for each."""
        words, ms_known = await known()
        t = time.perf_counter()
        rows = await dic.fetch(RECOMMEND, words, level)
        return {"words": [dict(r) for r in rows], "ms": ms_known + (time.perf_counter() - t) * 1000}

    @server.tool()
    async def find_reading_sentences() -> dict[str, Any]:
        """Up to ten sentences with every content word known but one."""
        words, ms_known = await known()
        t = time.perf_counter()
        rows = await dic.fetch(READING, words)
        return {"sentences": [dict(r) for r in rows], "ms": ms_known + (time.perf_counter() - t) * 1000}

    return server


def summary(xs: list[float]) -> str:
    xs = sorted(xs)
    return f"{statistics.median(xs):.1f} / {xs[int(0.95 * (len(xs) - 1))]:.1f} / {xs[-1]:.1f}"


async def main() -> None:
    jit = sys.argv[1]
    dic = await asyncpg.create_pool(DSN.format(db="openjlpt"), min_size=1, max_size=2, server_settings={"jit": jit})
    order = [r[0] for r in await dic.fetch("SELECT id FROM ojlpt.word_level ORDER BY level DESC, commonness, id")]
    app_c = await asyncpg.connect(DSN.format(db="app"))
    await app_c.execute(
        "DROP TABLE IF EXISTS learner_word_oj; CREATE TABLE learner_word_oj "
        "(learner_id integer, vocab_id text, PRIMARY KEY (learner_id, vocab_id))"
    )
    rows = [(s, w) for s in SIZES for w in order[:s]]
    rows += [(lid, w) for lid in range(1000, 6000) for w in order[: 50 + (lid * 7919) % 751]]
    await app_c.copy_records_to_table("learner_word_oj", records=rows)
    await app_c.execute("ANALYZE learner_word_oj")
    await app_c.close()
    app = await asyncpg.create_pool(DSN.format(db="app"), min_size=1, max_size=2)
    print(f"OpenJLPT tables, jit {jit}; learner_word_oj rows: {len(rows):,}.\n")
    print("| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |")
    print("|---|---|---|---|---|---|")
    worst, samples = 0.0, {}
    for level in LEVELS:
        for size in SIZES:
            async with Client(build(app, dic, size)) as client:
                for tool, args, key in (
                    ("recommend_words", {"level": level}, "words"),
                    ("find_reading_sentences", {}, "sentences"),
                ):
                    if tool == "find_reading_sentences" and level != LEVELS[0]:
                        continue
                    trip, sql, out = [], [], {}
                    for i in range(WARMUP + RUNS):
                        t = time.perf_counter()
                        res = await client.call_tool(tool, args)
                        ms = (time.perf_counter() - t) * 1000
                        out = json.loads(res.content[0].text)  # pyright: ignore
                        if i >= WARMUP:
                            trip.append(ms)
                            sql.append(out["ms"])
                    worst = max(worst, max(trip))
                    samples[f"{tool} N{level} known={size}"] = out[key][:4]
                    print(f"| N{level} | {size} | `{tool}` | {summary(trip)} | {summary(sql)} | {len(out[key])} |")
    print(f"\nWorst single round trip: **{worst:.1f} ms** (limit 200 ms).\n")
    print("<details><summary>First four results of each run</summary>\n\n```json")
    print(json.dumps(samples, ensure_ascii=False, indent=1, default=str))
    print("```\n</details>")
    await app.close()
    await dic.close()


if __name__ == "__main__":
    asyncio.run(main())
