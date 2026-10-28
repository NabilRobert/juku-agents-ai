"""Spike 1 (OpenJLPT): one COPY file per table from OpenJLPT's SQLite.

Plain standard-library code: a throwaway spike script, lighter than adding
pgloader (the off-the-shelf choice for slice 1). Opens the SQLite read-only.
Example sentences are also unnested into their own table, since Juku
queries them by word.

Usage: python3 -I sqlite_to_tsv.py <openjlpt.sqlite> <out dir>
"""

import json
import sqlite3
import sys
from pathlib import Path

LEVEL = {"N5": 5, "N4": 4, "N3": 3, "N2": 2, "N1": 1}


def cell(v: object) -> str:
    if v is None:
        return r"\N"
    return str(v).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def main(db: str, out: str) -> None:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    counts: dict[str, int] = {}

    def write(table: str, rows: list[tuple[object, ...]]) -> None:
        with (out_dir / f"{table}.tsv").open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write("\t".join(cell(v) for v in r) + "\n")
        counts[table] = len(rows)

    vocab = con.execute(
        "SELECT id, word, reading, romaji, meanings, level, pos, jmdict_id, other_forms, other_readings, examples"
        " FROM vocab ORDER BY id"
    ).fetchall()
    write("vocab", [(*r[:5], LEVEL[r[5]], *r[6:]) for r in vocab])
    examples: list[tuple[object, ...]] = []
    for r in vocab:
        for i, ex in enumerate(json.loads(r[10]), 1):
            examples.append((r[0], i, ex.get("ja"), ex.get("furigana"), ex.get("en"), ex.get("tatoeba_id")))
    write("vocab_example", examples)
    kanji = con.execute(
        "SELECT character, level, strokes, grade, freq, radical, radical_number, onyomi, kunyomi, nanori,"
        " meanings, words, supplementary FROM kanji ORDER BY character"
    ).fetchall()
    write("kanji", [(r[0], LEVEL[r[1]], *r[2:12], bool(r[12])) for r in kanji])
    grammar = con.execute(
        "SELECT id, pattern, reading, romaji, level, meaning, formation, examples, tags, notes FROM grammar ORDER BY id"
    ).fetchall()
    write("grammar", [(*r[:4], LEVEL[r[4]], *r[5:]) for r in grammar])
    write("pos", con.execute("SELECT code, description FROM pos ORDER BY code").fetchall())
    for table, n in sorted(counts.items()):
        print(f"{table}\t{n}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
