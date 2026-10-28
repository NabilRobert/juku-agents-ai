"""Spike 2: Juku's MCP server prototype with the two queries under test.

- `recommend_words`: i+1 with kanji leverage (ADR-010).
- `find_reading_sentences`: Tatoeba sentences whose content words are all
  known but one (LE4).

No tool takes a learner ID (ADR-006). Here the learner is fixed when the
server is built; spike 6 binds it to a signed token instead. The learner's
known words live in the app database and the dictionary in its own, so the
server reads the known words first and passes them to the dictionary query
as an array: Postgres can't join across databases.
"""

from __future__ import annotations

import time
from typing import Any

import asyncpg
from mcp.server.mcpserver import MCPServer

KNOWN_WORDS = "SELECT ent_seq FROM learner_word WHERE learner_id = $1 AND known"

RECOMMEND_V1 = """
WITH known_kanji AS (
    SELECT kanji FROM dict.kanji_level WHERE level > $2          -- every kanji of the easier levels
    UNION
    SELECT wk.kanji FROM dict.word_kanji wk WHERE wk.ent_seq = ANY ($1::int[])),  -- and those in known words
cand AS (
    SELECT w.*, ARRAY(SELECT wk.kanji FROM dict.word_kanji wk
                      WHERE wk.ent_seq = w.ent_seq AND wk.kanji NOT IN (SELECT kanji FROM known_kanji)) AS new_kanji
    FROM dict.word_level w
    WHERE w.level >= $2 AND w.ent_seq <> ALL ($1::int[])),         -- at the learner's level or easier, not known
scored AS (
    SELECT c.*, c.new_kanji[1] AS new_k, coalesce(kl.common_words, 0) AS leverage
    FROM cand c LEFT JOIN dict.kanji_leverage kl ON kl.kanji = c.new_kanji[1] AND kl.level = $2
    WHERE cardinality(c.new_kanji) <= 1),                          -- at most one unknown kanji
ranked AS (
    SELECT s.*, row_number() OVER (
        ORDER BY common DESC, (level > $2) DESC, leverage DESC, freq_band, ent_seq) AS rk
    FROM scored s),
varied AS (
    SELECT r.*, row_number() OVER (PARTITION BY new_k ORDER BY rk) AS nth FROM ranked r)
SELECT ent_seq, written, reading, level, new_k, leverage,
       CASE WHEN level > $2 THEN format('Kata N%s yang belum dikuasai. ', level) ELSE '' END
       || CASE WHEN new_k IS NULL THEN 'Tanpa kanji baru.'
               ELSE format('1 kanji baru: %s, muncul di %s kata umum N%s.', new_k, leverage, $2) END AS reason
FROM varied
WHERE new_k IS NULL OR nth <= 3                                    -- at most 3 of 10 share a new kanji
ORDER BY rk
LIMIT 10
"""

# v2: the same rules, with each candidate's unknown kanji computed once by a
# join. v1's correlated ARRAY subquery is planned three times, which inflates
# the cost estimate enough to trigger JIT compilation (about 300 ms).
RECOMMEND = """
WITH known_kanji AS (
    SELECT kanji FROM dict.kanji_level WHERE level > $2          -- every kanji of the easier levels
    UNION
    SELECT wk.kanji FROM dict.word_kanji wk WHERE wk.ent_seq = ANY ($1::int[])),  -- and those in known words
cand AS (
    SELECT w.ent_seq, w.written, w.reading, w.level, w.common, w.freq_band,
           count(wk.kanji) FILTER (WHERE kk.kanji IS NULL) AS n_new,
           min(wk.kanji) FILTER (WHERE kk.kanji IS NULL) AS new_k
    FROM dict.word_level w
    LEFT JOIN dict.word_kanji wk ON wk.ent_seq = w.ent_seq
    LEFT JOIN known_kanji kk ON kk.kanji = wk.kanji
    WHERE w.level >= $2 AND w.ent_seq <> ALL ($1::int[])          -- at the learner's level or easier, not known
    GROUP BY w.ent_seq),
scored AS (
    SELECT c.*, coalesce(kl.common_words, 0) AS leverage
    FROM cand c LEFT JOIN dict.kanji_leverage kl ON kl.kanji = c.new_k AND kl.level = $2
    WHERE c.n_new <= 1),                                           -- at most one unknown kanji
ranked AS (
    SELECT s.*, row_number() OVER (
        ORDER BY common DESC, (level > $2) DESC, leverage DESC, freq_band, ent_seq) AS rk
    FROM scored s),
varied AS (
    SELECT r.*, row_number() OVER (PARTITION BY new_k ORDER BY rk) AS nth FROM ranked r)
SELECT ent_seq, written, reading, level, new_k, leverage,
       CASE WHEN level > $2 THEN format('Kata N%s yang belum dikuasai. ', level) ELSE '' END
       || CASE WHEN new_k IS NULL THEN 'Tanpa kanji baru.'
               ELSE format('1 kanji baru: %s, muncul di %s kata umum N%s.', new_k, leverage, $2) END AS reason
FROM varied
WHERE new_k IS NULL OR nth <= 3                                    -- at most 3 of 10 share a new kanji
ORDER BY rk
LIMIT 10
"""

READING = """
WITH hits AS (
    SELECT sw.sentence_id, count(*) AS known_n
    FROM dict.sentence_word sw WHERE sw.ent_seq = ANY ($1::int[]) GROUP BY sw.sentence_id),
one_unknown AS (
    SELECT ss.sentence_id FROM dict.sentence_size ss JOIN hits h USING (sentence_id)
    WHERE ss.content_words - h.known_n = 1
    UNION ALL
    SELECT ss.sentence_id FROM dict.sentence_size ss
    WHERE ss.content_words = 1
      AND NOT EXISTS (SELECT 1 FROM hits h WHERE h.sentence_id = ss.sentence_id)),
found AS (
    SELECT o.sentence_id, s.text,
           (SELECT sw.ent_seq FROM dict.sentence_word sw
            WHERE sw.sentence_id = o.sentence_id AND sw.ent_seq <> ALL ($1::int[]) LIMIT 1) AS new_word,
           (SELECT i.text FROM dict.tatoeba_link l JOIN dict.tatoeba_sentence i ON i.id = l.ind_id
            WHERE l.jpn_id = o.sentence_id ORDER BY i.id LIMIT 1) AS indonesian
    FROM one_unknown o JOIN dict.tatoeba_sentence s ON s.id = o.sentence_id)
SELECT * FROM found
ORDER BY indonesian IS NULL, length(text), sentence_id               -- with a translation first, then shortest
LIMIT 10
"""


def build(app_pool: asyncpg.Pool, dict_pool: asyncpg.Pool, learner_id: int, recommend: str = RECOMMEND) -> MCPServer:
    server = MCPServer("juku-spike2")

    async def known() -> tuple[list[int], float]:
        t = time.perf_counter()
        rows = await app_pool.fetch(KNOWN_WORDS, learner_id)
        return [r["ent_seq"] for r in rows], (time.perf_counter() - t) * 1000

    @server.tool()
    async def recommend_words(level: int) -> dict[str, Any]:
        """Ten words to learn next, with a reason for each. level: 5 = N5 ... 2 = N2."""
        words, ms_known = await known()
        t = time.perf_counter()
        rows = await dict_pool.fetch(recommend, words, level)
        return {"words": [dict(r) for r in rows], "ms_known": ms_known, "ms_query": (time.perf_counter() - t) * 1000}

    @server.tool()
    async def find_reading_sentences() -> dict[str, Any]:
        """Up to ten sentences in which every content word is known but one."""
        words, ms_known = await known()
        t = time.perf_counter()
        rows = await dict_pool.fetch(READING, words)
        return {
            "sentences": [dict(r) for r in rows],
            "ms_known": ms_known,
            "ms_query": (time.perf_counter() - t) * 1000,
        }

    return server
