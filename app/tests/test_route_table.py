"""The web app's route table is a contract, kept in a snapshot (tests/snapshots/routes.json).

Each route's methods, path, endpoint name, response class, status code
and dependencies (by name, nested, in order). A refactor that moves
routes between files must leave this unchanged; a change to a route must
change the snapshot in the same commit, where a reviewer sees it.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from juku_app.web import create_web_app
from juku_data.engine import Databases
from web_helpers import deps

SNAPSHOT = Path(__file__).parent / "snapshots" / "routes.json"


def dependency_names(dependant: Dependant) -> list[Any]:
    """Each dependency's name, with its own dependencies under it, as FastAPI resolves them."""
    names: list[Any] = []
    for child in dependant.dependencies:
        name = getattr(child.call, "__name__", repr(child.call))
        nested = dependency_names(child)
        names.append([name, nested] if nested else name)
    return names


def route_table(app: FastAPI) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        response_class: Any = route.response_class
        table.append(
            {
                "methods": sorted(route.methods or set[str]()),
                "path": route.path,
                "name": route.name,
                "response_class": getattr(response_class, "value", response_class).__name__,
                "status_code": route.status_code,
                "dependencies": dependency_names(route.dependant),
            }
        )
    return sorted(table, key=lambda entry: (entry["path"], entry["methods"]))


def test_the_routes_match_their_snapshot(engine_databases: Databases) -> None:
    app = create_web_app(deps(engine_databases))
    assert route_table(app) == json.loads(SNAPSHOT.read_text(encoding="utf-8"))
