"""Spike 4: the JLPT CSVs (Waller's lists, with stephenmk's hand-added
JMdict IDs) as one COPY file. Usage: python3 -I jlpt_tsv.py <dir with n1..n5.csv> > jlpt.tsv"""

import csv
import sys
from pathlib import Path


def cell(v: str) -> str:
    v = v.strip()
    return r"\N" if not v else v.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")


for level in (5, 4, 3, 2, 1):
    with (Path(sys.argv[1]) / f"n{level}.csv").open(encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), 1):
            fields = [str(level), str(i), row["jmdict_seq"], row["kana"], row["kanji"], row["waller_definition"]]
            print("\t".join(cell(v) for v in fields))
