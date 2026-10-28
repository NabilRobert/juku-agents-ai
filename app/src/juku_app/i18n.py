"""Indonesian copy, kept out of the templates (scale path gap 17; Phase 2 UI1).

Templates say `{{ _("Recommendations") }}`; the Indonesian is in
locale/id/LC_MESSAGES/messages.po, a standard gettext catalogue Babel
reads. Another interface language later is another catalogue, not new
templates. A phrase missing from the catalogue shows in English rather
than breaking the page, and a test fails until it's translated.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from babel.messages.pofile import read_po

LOCALE = "id"
CATALOGUE = Path(__file__).parent / "locale" / LOCALE / "LC_MESSAGES" / "messages.po"


@cache
def translations() -> dict[str, str]:
    with CATALOGUE.open("rb") as file:
        catalogue = read_po(file, locale=LOCALE)
    return {str(message.id): str(message.string) for message in catalogue if message.id and message.string}


def gettext(phrase: str) -> str:
    return translations().get(phrase, phrase)


def ngettext(singular: str, plural: str, count: int) -> str:
    return gettext(singular if count == 1 else plural)
