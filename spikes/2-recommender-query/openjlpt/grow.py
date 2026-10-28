"""Spike 2 (OpenJLPT): both queries with 500-4,000 known words, direct SQL,
jit off. Usage: python grow.py > results-growth.md"""

import asyncio
import statistics
import time

import asyncpg

from bench import READING, RECOMMEND


async def main() -> None:
    c = await asyncpg.connect("postgresql://postgres@127.0.0.1:55437/openjlpt", server_settings={"jit": "off"})
    order = [r[0] for r in await c.fetch("SELECT id FROM ojlpt.word_level ORDER BY level DESC, commonness, id")]
    print("| Known words | Query | ms (p50 / p95 / max), 30 runs |\n|---|---|---|")
    for n in (500, 1000, 2000, 4000):
        for name, sql, args in (("recommend N3", RECOMMEND, (order[:n], 3)), ("reading", READING, (order[:n],))):
            stmt = await c.prepare(sql)
            xs = []
            for i in range(35):
                t = time.perf_counter()
                await stmt.fetch(*args)
                if i >= 5:
                    xs.append((time.perf_counter() - t) * 1000)
            xs.sort()
            print(f"| {n:,} | {name} | {statistics.median(xs):.1f} / {xs[int(0.95 * 29)]:.1f} / {xs[-1]:.1f} |")
    await c.close()


asyncio.run(main())
