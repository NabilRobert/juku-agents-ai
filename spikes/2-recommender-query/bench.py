"""Spike 2: time both tools through the MCP server prototype, for learners
who know 0, 100 and 500 words, at each level N5-N2.

Sets up the app database: three fixture learners, plus 5,000 synthetic ones
so learner_word has a realistic size (about 1.5 million rows). Needs spike 1's
container (juku-dict on 127.0.0.1:55437) with spikes 4 and 2's tables.

Usage: python bench.py <v1|v2> <jit on|off> > results-<v>-jit-<on|off>.md
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

from server import RECOMMEND, RECOMMEND_V1, build

DSN = "postgresql://postgres@127.0.0.1:55437/{db}"
SIZES = (0, 100, 500)
LEVELS = (5, 4, 3, 2)
WARMUP, RUNS = 5, 50

APP_SCHEMA = """
DROP TABLE IF EXISTS learner_word;
CREATE TABLE learner_word (learner_id integer NOT NULL, ent_seq integer NOT NULL, known boolean NOT NULL,
                           PRIMARY KEY (learner_id, ent_seq));
"""


async def setup_app(words: list[int]) -> None:
    admin = await asyncpg.connect(DSN.format(db="postgres"))
    if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = 'app'"):
        await admin.execute("CREATE DATABASE app")
    await admin.close()
    app = await asyncpg.connect(DSN.format(db="app"))
    await app.execute(APP_SCHEMA)
    rows: list[tuple[int, int, bool]] = []
    for size in SIZES:  # fixture learners 0, 100 and 500 know the n easiest words
        rows += [(size, w, True) for w in words[:size]]
    for learner in range(1000, 6000):  # synthetic learners: 50 to 800 words each, deterministic
        n = 50 + (learner * 7919) % 751
        rows += [(learner, w, True) for w in words[:n]]
    await app.copy_records_to_table("learner_word", records=rows)
    await app.execute("ANALYZE learner_word")
    print(f"<!-- learner_word rows: {len(rows):,} -->")
    await app.close()


def summary(xs: list[float]) -> str:
    xs = sorted(xs)
    p95 = xs[int(0.95 * (len(xs) - 1))]
    return f"{statistics.median(xs):.1f} / {p95:.1f} / {xs[-1]:.1f}"


async def main() -> None:
    version, jit = sys.argv[1], sys.argv[2]
    recommend = {"v1": RECOMMEND_V1, "v2": RECOMMEND}[version]
    dict_pool = await asyncpg.create_pool(DSN.format(db="dict"), min_size=1, max_size=2, server_settings={"jit": jit})
    print(f"Query {version}, jit {jit}.\n")
    easiest = await dict_pool.fetch(
        "SELECT ent_seq FROM dict.word_level ORDER BY level DESC, common DESC, freq_band, ent_seq"
    )
    await setup_app([r["ent_seq"] for r in easiest])
    app_pool = await asyncpg.create_pool(DSN.format(db="app"), min_size=1, max_size=2)

    print("| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |")
    print("|---|---|---|---|---|---|")
    samples: dict[str, Any] = {}
    worst = 0.0
    for level in LEVELS:
        for size in SIZES:
            async with Client(build(app_pool, dict_pool, learner_id=size, recommend=recommend)) as client:
                for tool, args, key in (
                    ("recommend_words", {"level": level}, "words"),
                    ("find_reading_sentences", {}, "sentences"),
                ):
                    if tool == "find_reading_sentences" and level != LEVELS[0]:
                        continue  # it doesn't depend on the level
                    trip: list[float] = []
                    sql: list[float] = []
                    out: dict[str, Any] = {}
                    for i in range(WARMUP + RUNS):
                        t = time.perf_counter()
                        result = await client.call_tool(tool, args)
                        ms = (time.perf_counter() - t) * 1000
                        out = json.loads(result.content[0].text)  # pyright: ignore
                        if i >= WARMUP:
                            trip.append(ms)
                            sql.append(out["ms_known"] + out["ms_query"])
                    worst = max(worst, max(trip))
                    samples[f"{tool} N{level} known={size}"] = out[key][:5]
                    print(f"| N{level} | {size} | `{tool}` | {summary(trip)} | {summary(sql)} | {len(out[key])} |")
    print(f"\nWorst single round trip: **{worst:.1f} ms** (limit 200 ms).\n")
    print("<details><summary>First five results of each run</summary>\n\n```json")
    print(json.dumps(samples, ensure_ascii=False, indent=1, default=str))
    print("```\n</details>")
    await app_pool.close()
    await dict_pool.close()


if __name__ == "__main__":
    sys.path.insert(0, ".")
    asyncio.run(main())
