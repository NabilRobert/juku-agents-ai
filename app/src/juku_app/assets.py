"""The script and style tags for the pages' Vue app, and the data each page hands it (ADR-024, revised 2026-11-05).

Every page is a Vue component (`app/web/src/pages/<Name>.vue`) mounted by one
entry, `src/main.ts`, which loads only that page's chunk. The server still
owns the data, the translations and the forms: a template puts the page's
props into a JSON script tag (`json_script`), and the component reads them.
Vite writes hashed files and a manifest mapping each source to its output.
Without a build (the Python tests), a page's HTML still carries all its data.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any, cast

from markupsafe import Markup, escape
from pydantic_core import to_jsonable_python

STATIC = Path(__file__).parent / "static"
MANIFEST = STATIC / "dist" / ".vite" / "manifest.json"
STATIC_URL = "/static/dist/"
# Characters that could end the script tag or start a comment inside it, written as JSON escapes instead.
UNSAFE_IN_SCRIPT = {"<": "\\u003c", ">": "\\u003e", "&": "\\u0026", "\u2028": "\\u2028", "\u2029": "\\u2029"}


@cache
def manifest() -> dict[str, Any]:
    if not MANIFEST.is_file():
        return {}
    return cast(dict[str, Any], json.loads(MANIFEST.read_text(encoding="utf-8")))


def stylesheet() -> Markup:
    """The shared Tailwind stylesheet, if built."""
    entry = manifest().get("src/styles.css")
    if not entry:
        return Markup("")
    return Markup('<link rel="stylesheet" href="{}">').format(STATIC_URL + str(entry["file"]))


def _module(source: str) -> Markup:
    """The module script (deferred by being a module) and CSS for one built entry, or nothing without a build."""
    entry = manifest().get(source)
    if not entry:
        return Markup("")
    tags = [f'<script type="module" src="{escape(STATIC_URL + str(entry["file"]))}"></script>']
    tags += [f'<link rel="stylesheet" href="{escape(STATIC_URL + str(css))}">' for css in entry.get("css", [])]
    return Markup("\n".join(tags))  # noqa: S704 (every part is escaped above)


def island(name: str) -> Markup:
    """A script that isn't a page (`src/islands/<name>.ts`): the real-user timings every page sends."""
    return _module(f"src/islands/{name}.ts")


def page_app() -> Markup:
    """The Vue app that mounts the page's component."""
    return _module("src/main.ts")


def _plain(value: Any) -> Any:
    # Database rows (SQLAlchemy's RowMapping) are mappings that pydantic can't serialise by itself.
    if isinstance(value, Mapping):
        return {str(key): item for key, item in cast(Mapping[Any, Any], value).items()}
    raise TypeError(f"{type(value).__name__} can't be sent to a page as JSON: convert it in the route or template")


def json_script(element_id: str, value: Any) -> Markup:
    """`value` as JSON in a <script type="application/json"> tag, for the page's Vue component to read.

    Models, dates and rows become JSON; Japanese stays as written (not \\u escapes), so the HTML stays readable.
    """
    data = json.dumps(to_jsonable_python(value, fallback=_plain), ensure_ascii=False)
    for character, escaped in UNSAFE_IN_SCRIPT.items():
        data = data.replace(character, escaped)
    return Markup('<script type="application/json" id="{}">').format(element_id) + Markup(data) + Markup("</script>")  # noqa: S704 (the JSON can't close the tag: see UNSAFE_IN_SCRIPT)
