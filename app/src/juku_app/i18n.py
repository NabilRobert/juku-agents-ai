"""The pages' words in Indonesian or English (scale path gap 17; Phase 2 UI1; Arthur's switch, 2026-11-05).

Templates say `{{ _("Recommendations") }}`; the Indonesian is in
locale/id/LC_MESSAGES/messages.po, a standard gettext catalogue Babel
reads. A phrase missing from the catalogue shows in English rather than
breaking the page, and a test fails until it's translated.

The phrases are written in English, so English needs no catalogue: the
learner's choice (kept in their session, `/bahasa`) is set for each
request by `use_language`, in a context variable, so one learner's choice
never reaches another's request.
"""

from __future__ import annotations

from contextvars import ContextVar
from functools import cache
from pathlib import Path

from babel.messages.pofile import read_po

LOCALE = "id"
CATALOGUE = Path(__file__).parent / "locale" / LOCALE / "LC_MESSAGES" / "messages.po"
LANGUAGES = ("id", "en")
DEFAULT_LANGUAGE = "id"
_language: ContextVar[str] = ContextVar("language", default=DEFAULT_LANGUAGE)


def use_language(language: object) -> str:
    """Set this request's language; anything but a known one means the default. Returns what was set."""
    chosen = language if isinstance(language, str) and language in LANGUAGES else DEFAULT_LANGUAGE
    _language.set(chosen)
    return chosen


@cache
def translations() -> dict[str, str]:
    with CATALOGUE.open("rb") as file:
        catalogue = read_po(file, locale=LOCALE)
    return {str(message.id): str(message.string) for message in catalogue if message.id and message.string}


def gettext(phrase: str) -> str:
    if _language.get() == "en":
        return phrase
    return translations().get(phrase, phrase)


def ngettext(singular: str, plural: str, count: int) -> str:
    return gettext(singular if count == 1 else plural)
