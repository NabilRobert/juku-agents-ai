"""The script and style tags for each page's Vue island (ADR-024; Phase 2 FE1, FE2).

Vite builds one small bundle per island (app/web/vite.config.ts) and a
manifest mapping each source file to its hashed output. A page asks for
its island by name and gets exactly that bundle and its CSS, nothing for
the other pages. Without a build (the Python tests), a page still renders,
server-side and complete, just without the interactive part.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, cast

from markupsafe import Markup, escape

STATIC = Path(__file__).parent / "static"
MANIFEST = STATIC / "dist" / ".vite" / "manifest.json"
STATIC_URL = "/static/dist/"


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


def island(name: str) -> Markup:
    """The module script for one island (`src/islands/<name>.ts`), deferred by being a module."""
    entry = manifest().get(f"src/islands/{name}.ts")
    if not entry:
        return Markup("")
    tags = [f'<script type="module" src="{escape(STATIC_URL + str(entry["file"]))}"></script>']
    tags += [f'<link rel="stylesheet" href="{escape(STATIC_URL + str(css))}">' for css in entry.get("css", [])]
    return Markup("\n".join(tags))  # noqa: S704 (every part is escaped above)
