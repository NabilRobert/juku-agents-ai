"""Furigana as real markup (Phase 2 FE4): OpenJLPT's `{漢字|かんじ}` becomes `<ruby>`.

<ruby> is read by screen readers and needs no script. Everything is
escaped first; only the ruby tags are added.
"""

from __future__ import annotations

from juku_data.dictionary.furigana import FURIGANA_MARKUP
from markupsafe import Markup, escape


def furigana_to_ruby(furigana: str) -> Markup:
    parts: list[str] = []
    position = 0
    for match in FURIGANA_MARKUP.finditer(furigana):
        parts.append(str(escape(furigana[position : match.start()])))
        parts.append(f"<ruby>{escape(match.group(1))}<rt>{escape(match.group(2))}</rt></ruby>")
        position = match.end()
    parts.append(str(escape(furigana[position:])))
    return Markup("".join(parts))  # noqa: S704 (every part is escaped above)
