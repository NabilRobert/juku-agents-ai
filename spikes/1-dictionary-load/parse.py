"""Spike 1: turn the raw dictionary downloads into TSV files for COPY.

Standard library only. Reads data/raw (untrusted downloads) and writes one
TSV per table into an output directory, in Postgres COPY text format.

Usage: python3 -I parse.py <raw dir> <out dir>
"""

from __future__ import annotations

import bz2
import gzip
import io
import re
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

ENTITY_DECL = re.compile(r'<!ENTITY\s+([A-Za-z0-9_.-]+)\s+"([^"]*)">')


def cell(value: object) -> str:
    """One COPY text-format field."""
    if value is None:
        return r"\N"
    if isinstance(value, bool):
        return "t" if value else "f"
    if isinstance(value, list):
        value = array(value)  # pyright: ignore[reportUnknownArgumentType]
        if value is None:
            return r"\N"
    s = str(value)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def array(items: list[object]) -> str | None:
    """A Postgres text[] literal, or NULL when empty."""
    if not items:
        return None
    quoted = ('"' + str(i).replace("\\", "\\\\").replace('"', '\\"') + '"' for i in items)
    return "{" + ",".join(quoted) + "}"


class Writer:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.files: dict[str, io.TextIOWrapper] = {}
        self.counts: dict[str, int] = {}

    def row(self, table: str, *values: object) -> None:
        f = self.files.get(table)
        if f is None:
            f = self.files[table] = (self.out / f"{table}.tsv").open("w", encoding="utf-8", newline="\n")
            self.counts[table] = 0
        f.write("\t".join(cell(v) for v in values) + "\n")
        self.counts[table] += 1

    def close(self) -> None:
        for f in self.files.values():
            f.close()


def jmdict_source(path: Path, w: Writer) -> io.BytesIO:
    """JMdict with every entity's value replaced by its own name, so POS and
    misc fields keep their codes (v5r, uk...). The codes and descriptions go
    to their own table."""
    text = gzip.decompress(path.read_bytes()).decode("utf-8")
    head, _, body = text.partition("]>")
    seen: set[str] = set()
    for code, description in ENTITY_DECL.findall(head):
        # The DTD declares `ik` twice, identically; XML keeps the first.
        if code not in seen:
            seen.add(code)
            w.row("jmdict_entity", code, description)
    head = ENTITY_DECL.sub(lambda m: f'<!ENTITY {m.group(1)} "{m.group(1)}">', head)
    created = re.search(r"JMdict created: (\S+)", body)
    w.row("dict_version", "JMdict_e", created.group(1) if created else None)
    return io.BytesIO((head + "]>" + body).encode("utf-8"))


def texts(el: ET.Element, tag: str) -> list[str]:
    return [c.text or "" for c in el.findall(tag)]


def parse_jmdict(path: Path, w: Writer) -> None:
    for _, entry in ET.iterparse(jmdict_source(path, w), events=("end",)):
        if entry.tag != "entry":
            continue
        seq = int(entry.findtext("ent_seq") or "0")
        w.row("jmdict_entry", seq)
        for i, k in enumerate(entry.findall("k_ele"), 1):
            w.row("jmdict_kanji", seq, i, k.findtext("keb"), texts(k, "ke_inf"), texts(k, "ke_pri"))
        for i, r in enumerate(entry.findall("r_ele"), 1):
            w.row(
                "jmdict_reading",
                seq,
                i,
                r.findtext("reb"),
                r.find("re_nokanji") is not None,
                texts(r, "re_restr"),
                texts(r, "re_inf"),
                texts(r, "re_pri"),
            )
        for i, s in enumerate(entry.findall("sense"), 1):
            w.row(
                "jmdict_sense",
                seq,
                i,
                texts(s, "pos"),
                texts(s, "field"),
                texts(s, "misc"),
                texts(s, "dial"),
                texts(s, "stagk"),
                texts(s, "stagr"),
                texts(s, "xref"),
                texts(s, "s_inf"),
            )
            for j, g in enumerate(s.findall("gloss"), 1):
                w.row("jmdict_gloss", seq, i, j, g.text or "", g.get("g_type"))
        entry.clear()


def parse_kanjidic(path: Path, w: Writer) -> None:
    root = ET.parse(gzip.open(path)).getroot()
    header = root.find("header")
    w.row("dict_version", "KANJIDIC2", header.findtext("database_version") if header is not None else None)
    for c in root.iter("character"):
        misc = c.find("misc")
        rad = c.find("radical/rad_value[@rad_type='classical']")
        readings = c.findall("reading_meaning/rmgroup/reading")
        meanings = [m.text or "" for m in c.findall("reading_meaning/rmgroup/meaning") if m.get("m_lang") is None]

        def num(tag: str, misc: ET.Element | None = misc) -> int | None:
            v = misc.findtext(tag) if misc is not None else None
            return int(v) if v else None

        w.row(
            "kanjidic_char",
            c.findtext("literal"),
            num("grade"),
            num("stroke_count"),
            num("freq"),
            num("jlpt"),
            int(rad.text) if rad is not None and rad.text else None,
            [r.text for r in readings if r.get("r_type") == "ja_on"],
            [r.text for r in readings if r.get("r_type") == "ja_kun"],
            meanings,
            texts(c, "reading_meaning/nanori"),
        )


def parse_kradfile(path: Path, w: Writer) -> None:
    with zipfile.ZipFile(path) as z:
        for name in ("kradfile", "kradfile2"):
            for line in z.read(name).decode("euc_jp").splitlines():
                if not line or line.startswith("#"):
                    continue
                kanji, _, parts = line.partition(" : ")
                w.row("kradfile", kanji.strip(), parts.split(), name)


def tsv_lines(path: Path) -> Iterator[list[str]]:
    with bz2.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n").split("\t")


# One token of Tatoeba's index (the WWWJDIC "B line" format):
# headword(reading)[sense]{surface form}~, everything after the headword optional.
INDEX_TOKEN = re.compile(r"^([^()\[\]{}~]+)(?:\(([^()]*)\))?(?:\[(\d+)\])?(?:\{([^{}]*)\})?(~)?$")


def parse_tatoeba(raw: Path, w: Writer) -> None:
    for lang in ("jpn", "ind"):
        for sid, lng, text in tsv_lines(raw / f"{lang}_sentences.tsv.bz2"):
            w.row("tatoeba_sentence", int(sid), lng, text)
    for jpn, ind in tsv_lines(raw / "jpn-ind_links.tsv.bz2"):
        w.row("tatoeba_link", int(jpn), int(ind))
    unparsed = 0
    with tarfile.open(raw / "jpn_indices.tar.bz2") as tar:
        member = tar.extractfile("jpn_indices.csv")
        assert member is not None
        # Keyed by line: 105 (sentence, meaning) pairs appear on more than one line.
        for line_no, line in enumerate(io.TextIOWrapper(member, encoding="utf-8"), 1):
            sid, meaning_id, text = line.rstrip("\n").split("\t")
            for i, token in enumerate(text.split(), 1):
                m = INDEX_TOKEN.match(token)
                if m is None:
                    unparsed += 1
                    w.row("tatoeba_index_unparsed", line_no, int(sid), i, token)
                    continue
                # "(#1392580)" in the reading's place is a JMdict entry ID, not a reading.
                reading, ent_seq = m.group(2), None
                if reading is not None and reading.startswith("#") and reading[1:].isdigit():
                    reading, ent_seq = None, int(reading[1:])
                w.row(
                    "tatoeba_index",
                    line_no,
                    int(sid),
                    int(meaning_id),
                    i,
                    m.group(1),
                    reading,
                    ent_seq,
                    int(m.group(3)) if m.group(3) else None,
                    m.group(4),
                    m.group(5) is not None,
                )
    print(f"tatoeba index tokens unparsed: {unparsed}", file=sys.stderr)


def main(argv: Iterable[str]) -> None:
    raw, out = (Path(a) for a in argv)
    out.mkdir(parents=True, exist_ok=True)
    w = Writer(out)
    parse_jmdict(raw / "edrdg" / "JMdict_e.gz", w)
    parse_kanjidic(raw / "edrdg" / "kanjidic2.xml.gz", w)
    parse_kradfile(raw / "edrdg" / "kradzip.zip", w)
    parse_tatoeba(raw / "tatoeba", w)
    w.close()
    for table, n in sorted(w.counts.items()):
        print(f"{table}\t{n}")


if __name__ == "__main__":
    main(sys.argv[1:])
