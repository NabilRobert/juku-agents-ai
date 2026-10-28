"""Spike 2 (OpenJLPT): the reading-practice index. Tokenizes OpenJLPT's
example sentences with SudachiPy and keeps the sentences whose every
content word maps to one word ID, as `ojlpt.sentence_word` and
`ojlpt.sentence_size`.

The token matching is copied from spike 4 (spike/jlpt-mapping, 17abe92,
openjlpt/completeness.py, `resolve`), because spike branches don't share
code. Slice 2 gets one shared version.

Usage: python sentences.py
"""

from __future__ import annotations

import asyncio
import json
import warnings
from collections import defaultdict
from typing import Any

import asyncpg
from sudachipy import Dictionary, SplitMode

warnings.filterwarnings("ignore", category=DeprecationWarning)
FUNCTION_POS = {"助詞", "助動詞", "補助記号", "記号", "空白", "接尾辞", "接頭辞"}
GRAMMAR_FORMS = {"ない", "なく", "なかっ", "なけれ"}  # grammar in OpenJLPT, not vocabulary


def hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def is_kana(s: str) -> bool:
    return all("ぁ" <= c <= "ゖ" or "ァ" <= c <= "ヺ" or c in "ー・ゝゞ" for c in s)


async def main() -> None:
    c = await asyncpg.connect("postgresql://postgres@127.0.0.1:55437/openjlpt")
    vocab = await c.fetch("SELECT id, word, reading, other_forms, other_readings FROM ojlpt.vocab")
    by_written: dict[str, set[str]] = defaultdict(set)
    by_reading: dict[str, set[str]] = defaultdict(set)
    reading_of: dict[str, set[str]] = {}
    for v in vocab:
        forms, readings = json.loads(v["other_forms"]), json.loads(v["other_readings"])
        reading_of[v["id"]] = {v["reading"], *readings}
        for f in (v["word"], *forms):
            by_written[f].add(v["id"])
        for r in (v["reading"], *readings):
            by_reading[r].add(v["id"])
    tok = Dictionary(dict="core").create(mode=SplitMode.C)
    fine = Dictionary(dict="core").create(mode=SplitMode.A)
    lemma: dict[str, str] = {}

    def lemma_kana(form: str) -> str:
        if form not in lemma:
            lemma[form] = "".join(hira(m.reading_form()) for m in tok.tokenize(form))
        return lemma[form]

    def resolve(m: Any) -> set[str]:
        d, norm = m.dictionary_form(), m.normalized_form()
        for ids in (by_written.get(d), by_written.get(norm), by_reading.get(d) if is_kana(d) else None):
            if ids:
                return ({i for i in ids if lemma_kana(d) in reading_of[i]} or ids) if len(ids) > 1 else ids
        return set()

    rows = await c.fetch(
        "SELECT DISTINCT ON (ja) vocab_id, ord, ja FROM ojlpt.vocab_example ORDER BY ja, vocab_id, ord"
    )
    words: list[tuple[int, str]] = []
    sizes: list[tuple[int, str, int]] = []
    for sid, r in enumerate(rows, 1):
        ids: set[str] = set()
        ok = True
        for m in tok.tokenize(r["ja"]):
            pos = m.part_of_speech()
            if pos[0] in FUNCTION_POS or pos[1] in {"固有名詞", "数詞"} or m.surface() in GRAMMAR_FORMS:
                continue
            found = resolve(m)
            if not found:
                units = [u for u in fine.tokenize(m.surface()) if u.part_of_speech()[0] not in FUNCTION_POS]
                if units and not (len(units) == 1 and units[0].surface() == m.surface()):
                    parts = [resolve(u) for u in units]
                    if all(len(p) == 1 for p in parts):
                        found = set().union(*parts)
                        ids |= found
                        continue
            if len(found) != 1:
                ok = False
                break
            ids |= found
        if ok and ids:
            words += [(sid, i) for i in sorted(ids)]
            sizes.append((sid, r["ja"], len(ids)))
    await c.execute("""
        DROP TABLE IF EXISTS ojlpt.sentence_word, ojlpt.sentence_size;
        CREATE TABLE ojlpt.sentence_size (
            sentence_id integer PRIMARY KEY, ja text NOT NULL, content_words smallint NOT NULL);
        CREATE TABLE ojlpt.sentence_word (
            sentence_id integer NOT NULL, id text NOT NULL, PRIMARY KEY (sentence_id, id));
    """)
    await c.copy_records_to_table("sentence_size", schema_name="ojlpt", records=sizes)
    await c.copy_records_to_table("sentence_word", schema_name="ojlpt", records=words)
    await c.execute(
        "CREATE INDEX ON ojlpt.sentence_word (id); CREATE INDEX ON ojlpt.sentence_size (content_words);"
        " ANALYZE ojlpt.sentence_word, ojlpt.sentence_size;"
    )
    print(f"distinct sentences {len(rows):,}; fully mapped {len(sizes):,}; sentence_word rows {len(words):,}")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())
