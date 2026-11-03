"""OpenJLPT's furigana markup, `{漢字|かんじ}`: its pattern, and the check that it spells its sentence.

With the markup taken out, furigana must spell exactly its sentence. Anything else isn't furigana,
so it's dropped before Shiori or a learner sees it: a sentence's fields are shown as they are, and
this is the one field whose content can be checked. Every furigana in OpenJLPT bf4e1ee passes
(10,517 of them).
"""

from __future__ import annotations

import re

FURIGANA_MARKUP = re.compile(r"\{([^|{}]+)\|([^{}]+)\}")


def spelled_by(furigana: str) -> str:
    """The text the furigana spells, without its readings."""
    return FURIGANA_MARKUP.sub(r"\1", furigana)


def checked_furigana(ja: str, furigana: str | None) -> str | None:
    """The furigana if it spells `ja`, otherwise None."""
    if furigana is None or spelled_by(furigana) != ja:
        return None
    return furigana
