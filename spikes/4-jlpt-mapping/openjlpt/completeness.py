"""Spike 4 (OpenJLPT): how complete is OpenJLPT for Juku?

1. Words with no JMdict link, and links that no longer resolve in the
   current JMdict (spike 1's `dict` database).
2. Agreement between OpenJLPT's JMdict IDs and this spike's own rule-based
   mapping of the same JLPT lists (`dict.jlpt_map`).
3. Words with no example sentence.
4. The i+1 question: the example sentences tokenized with SudachiPy (split
   mode C), and how many content tokens map back to one OpenJLPT word ID.

Plain code: a spike script. Usage:
    python completeness.py <openjlpt.sqlite> > results.md
"""

from __future__ import annotations

import asyncio
import json
import random
import sqlite3
import sys
import warnings
from collections import Counter, defaultdict
from typing import Any

import asyncpg
from sudachipy import Dictionary, SplitMode

warnings.filterwarnings("ignore", category=DeprecationWarning)
FUNCTION_POS = {"助詞", "助動詞", "補助記号", "記号", "空白", "接尾辞", "接頭辞"}


def hira(katakana: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in katakana)


def is_kana(s: str) -> bool:
    return all("ぁ" <= c <= "ゖ" or "ァ" <= c <= "ヺ" or c in "ー・ゝゞ" for c in s)


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "-"


async def dict_checks(vocab: list[dict[str, Any]]) -> dict[str, Any]:
    c = await asyncpg.connect("postgresql://postgres@127.0.0.1:55437/dict")
    current = {r[0] for r in await c.fetch("SELECT ent_seq FROM dict.jmdict_entry")}
    ours = await c.fetch(
        "SELECT level, kanji, kana, ent_seq, how FROM dict.jlpt_map WHERE how NOT IN ('ambiguous', 'unmatched')"
    )
    await c.close()
    linked = [v for v in vocab if v["jmdict_id"] is not None]
    gone = [v for v in linked if v["jmdict_id"] not in current]
    by_form: dict[tuple[str, str], set[int]] = defaultdict(set)
    for v in linked:
        by_form[(v["word"], v["reading"])].add(v["jmdict_id"])
    agree = differ = absent = 0
    examples_differ: list[str] = []
    for r in ours:
        key = (r["kanji"] or r["kana"], r["kana"])
        ids = by_form.get(key)
        if ids is None:
            absent += 1
        elif r["ent_seq"] in ids:
            agree += 1
        else:
            differ += 1
            if len(examples_differ) < 8:
                examples_differ.append(f"{key[0]} ({key[1]}): ours {r['ent_seq']}, OpenJLPT {sorted(ids)}")
    return {
        "linked": len(linked),
        "gone": gone,
        "agree": agree,
        "differ": differ,
        "absent": absent,
        "examples_differ": examples_differ,
    }


def main(db: str) -> None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    vocab = [dict(r) for r in con.execute("SELECT * FROM vocab ORDER BY id")]
    for v in vocab:
        v["examples"] = json.loads(v["examples"])
        v["other_forms"] = json.loads(v["other_forms"])
        v["other_readings"] = json.loads(v["other_readings"])
    n = len(vocab)
    levels = Counter(v["level"] for v in vocab)

    # Forms and readings -> word IDs
    by_written: dict[str, set[str]] = defaultdict(set)
    by_reading: dict[str, set[str]] = defaultdict(set)
    reading_of = {v["id"]: {v["reading"], *v["other_readings"]} for v in vocab}
    for v in vocab:
        for form in (v["word"], *v["other_forms"]):
            by_written[form].add(v["id"])
        for reading in (v["reading"], *v["other_readings"]):
            by_reading[reading].add(v["id"])

    tok = Dictionary(dict="core").create(mode=SplitMode.C)
    fine = Dictionary(dict="core").create(mode=SplitMode.A)
    lemma_reading: dict[str, str] = {}

    def lemma_kana(form: str) -> str:
        if form not in lemma_reading:
            lemma_reading[form] = "".join(hira(m.reading_form()) for m in tok.tokenize(form))
        return lemma_reading[form]

    def resolve(m: Any) -> tuple[str, set[str]]:
        d, norm = m.dictionary_form(), m.normalized_form()
        for how, ids in (
            ("written", by_written.get(d)),
            ("normalized", by_written.get(norm)),
            ("kana reading", by_reading.get(d) if is_kana(d) else None),
        ):
            if ids:
                if len(ids) > 1:  # homographs: keep the ones whose reading matches the lemma's
                    narrowed = {i for i in ids if lemma_kana(d) in reading_of[i]}
                    ids = narrowed or ids
                return how, ids
        return "unmatched", set()

    sentences: dict[str, list[tuple[str, str, set[str]]]] = {}
    for v in vocab:
        for ex in v["examples"]:
            ja = ex["ja"]
            if ja in sentences:
                continue
            toks: list[tuple[str, str, set[str]]] = []
            for m in tok.tokenize(ja):
                pos = m.part_of_speech()
                if pos[0] in FUNCTION_POS:
                    continue
                if pos[1] in {"固有名詞", "数詞"}:
                    toks.append((m.surface(), "name or number", set()))
                    continue
                how, ids = resolve(m)
                if not ids:
                    # A compound OpenJLPT doesn't list (私たち, 日本語): retry its finer units (mode A).
                    units = [u for u in fine.tokenize(m.surface()) if u.part_of_speech()[0] not in FUNCTION_POS]
                    if units and not (len(units) == 1 and units[0].surface() == m.surface()):
                        resolved = [resolve(u) for u in units]
                        if all(len(r[1]) == 1 for r in resolved):
                            how, ids = "split (mode A)", {"+".join(sorted(next(iter(r[1])) for r in resolved))}
                toks.append((m.surface(), how, ids))
            sentences[ja] = toks

    content = [t for toks in sentences.values() for t in toks if t[1] != "name or number"]
    unique = [t for t in content if len(t[2]) == 1]
    ambiguous = [t for t in content if len(t[2]) > 1]
    unmatched = [t for t in content if not t[2]]
    full = [s for s, toks in sentences.items() if all(len(t[2]) == 1 or t[1] == "name or number" for t in toks)]
    # Variant: ない and its forms counted as grammar (OpenJLPT lists it as grammar, not vocabulary).
    grammar_forms = {"ない", "なく", "なかっ", "なけれ"}
    full_nai = [
        s
        for s, toks in sentences.items()
        if all(len(t[2]) == 1 or t[1] == "name or number" or t[0] in grammar_forms for t in toks)
    ]

    checks = asyncio.run(dict_checks(vocab))
    no_example = [v for v in vocab if not v["examples"]]

    out = print
    out("# OpenJLPT completeness (spike 4)\n")
    out(
        f"OpenJLPT at the pinned commit: {n:,} words "
        f"({', '.join(f'{k} {levels[k]:,}' for k in ('N5', 'N4', 'N3', 'N2', 'N1'))}).\n"
    )
    out("## 1. JMdict links\n")
    unlinked = [v for v in vocab if v["jmdict_id"] is None]
    out(
        f"- Linked: {checks['linked']:,} ({pct(checks['linked'], n)}); **unlinked: {len(unlinked)}**: "
        + ", ".join(f"{v['word']} ({v['level']})" for v in unlinked)
    )
    out(
        f"- Links that don't resolve in JMdict_e 2026-10-28: **{len(checks['gone'])}**"
        + (": " + ", ".join(f"{v['word']} {v['jmdict_id']}" for v in checks["gone"][:20]) if checks["gone"] else "")
    )
    out("\n## 2. Against this spike's own rule-based mapping (same JLPT lists)\n")
    total = checks["agree"] + checks["differ"]
    out(
        f"- Same (spelling, reading) in both: {total:,}. Same JMdict ID: **{checks['agree']:,} "
        f"({pct(checks['agree'], total)})**; different: {checks['differ']}. "
        f"Not in OpenJLPT under that spelling: {checks['absent']:,}."
    )
    for e in checks["examples_differ"]:
        out(f"  - {e}")
    out("\n## 3. Examples\n")
    out(
        f"- Words with no example: **{len(no_example):,} ({pct(len(no_example), n)})**; by level: "
        + ", ".join(f"{k} {sum(1 for v in no_example if v['level'] == k)}" for k in ("N5", "N4", "N3", "N2", "N1"))
    )
    out(f"- Example rows: {sum(len(v['examples']) for v in vocab):,}; distinct sentences: {len(sentences):,}")
    out("\n## 4. Example tokens back to word IDs (SudachiPy, split mode C)\n")
    out(
        "Function words (particles, auxiliaries, affixes, symbols) are left out, as in LE4; names and numbers "
        "count as known.\n"
    )
    out("| | Tokens | Share of content tokens |\n|---|---|---|")
    out(f"| Content tokens | {len(content):,} | 100% |")
    for label, group in (
        ("One word ID", unique),
        ("Several IDs (homographs)", ambiguous),
        ("No OpenJLPT word", unmatched),
    ):
        out(f"| {label} | {len(group):,} | {pct(len(group), len(content))} |")
    hows = Counter(t[1] for t in unique)
    out(f"\nMatched by: {', '.join(f'{k} {v:,}' for k, v in hows.most_common())}.\n")
    out(
        f"**Sentences whose every content token maps to one word ID: {len(full):,} of {len(sentences):,} "
        f"({pct(len(full), len(sentences))})**: the pool for i+1 reading practice.\n"
    )
    share = pct(len(full_nai), len(sentences))
    out(f"Counting ない (なく, なかっ, なけれ) as grammar too: **{len(full_nai):,} ({share})**.\n")
    out(
        "Most frequent unmatched tokens: "
        + ", ".join(f"{s} ({c})" for s, c in Counter(t[0] for t in unmatched).most_common(25))
    )
    out(
        "\nMost frequent ambiguous tokens: "
        + ", ".join(f"{s} ({c})" for s, c in Counter(t[0] for t in ambiguous).most_common(15))
    )

    rng = random.Random(4)
    words = {v["id"]: v for v in vocab}
    sample = rng.sample(unique, 30)
    out("\n## Hand-check sample: 30 tokens mapped to one word\n")
    out("| Token | How | Word | Reading | First meaning |\n|---|---|---|---|---|")
    for surface, how, ids in sample:
        w = words[next(iter(ids)).split("+")[0]]
        out(f"| {surface} | {how} | {w['word']} | {w['reading']} | {json.loads(w['meanings'])[0]} |")


if __name__ == "__main__":
    main(sys.argv[1])
