"""The owner role (ADR-029): only the owner manages learners, each action is audited, and no learner becomes owner."""

from __future__ import annotations

from contextlib import aclosing

import httpx
import pytest
from fastapi.routing import APIRoute
from juku_app import owner
from juku_app.invites import issue_codes, redeem
from juku_app.web import create_web_app
from juku_data.engine import Databases
from pipeline_helpers import scalar
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from test_route_table import api_routes, dependency_names
from web_helpers import client_for, csrf_of, deps, sign_up

# The learner a code signed up: the tests share one database, so nicknames may repeat.
LEARNER_OF_CODE = """
SELECT l.public_id FROM app.invite_codes c JOIN learning.learners l ON l.id = c.learner_id WHERE c.lookup = :lookup
"""
ACTIONS_BY = """
SELECT count(*) FROM app.owner_actions a JOIN learning.learners o ON o.id = a.owner_id WHERE o.public_id = :p
"""


async def learners_with(db: Databases, public_id: str) -> int:
    return int(await scalar(db, "SELECT count(*) FROM learning.learners WHERE public_id = :p", p=public_id))


async def signed_up(db: Databases, nickname: str) -> tuple[httpx.AsyncClient, str]:
    """A signed-in client for a new learner, and their public ID. The caller closes the client."""
    code = (await issue_codes(db.app, 1))[0]
    client = client_for(deps(db))
    await sign_up(client, code, nickname=nickname)
    return client, str(await scalar(db, LEARNER_OF_CODE, lookup=code.split(".")[0]))


def owner_only_routes(db: Databases) -> list[APIRoute]:
    """Every route behind the owner guard, found from the app itself, so a new owner route is covered too."""
    app = create_web_app(deps(db))
    return [route for route in api_routes(list(app.routes)) if "admin" in str(dependency_names(route.dependant))]


async def test_a_new_learner_is_a_learner_not_an_owner(engine_databases: Databases) -> None:
    client, public_id = await signed_up(engine_databases, "Baru")
    await client.aclose()
    role = await scalar(engine_databases, "SELECT role FROM learning.learners WHERE public_id = :p", p=public_id)
    assert role == "learner"


async def test_every_owner_route_refuses_a_learner(engine_databases: Databases) -> None:
    routes = owner_only_routes(engine_databases)
    assert {route.path for route in routes} >= {"/admin/runs", "/admin/learners", "/admin/learners/codes"}
    client, public_id = await signed_up(engine_databases, "Biasa")
    async with aclosing(client):
        csrf = csrf_of(await client.get("/pengaturan"))
        for route in routes:
            path = route.path.replace("{run_id}", "1")
            for method in route.methods or set[str]():
                response = await client.request(method, path, data={"csrf": csrf, "count": "1", "public_id": "x"})
                assert response.status_code == 404, f"{method} {path} let a learner in"
    assert await scalar(engine_databases, ACTIONS_BY, p=public_id) == 0


async def test_a_learner_cannot_make_themselves_owner_through_any_form(engine_databases: Databases) -> None:
    client, public_id = await signed_up(engine_databases, "Licik")
    async with aclosing(client):
        csrf = csrf_of(await client.get("/pengaturan"))
        await client.post(
            "/pengaturan",
            data={"csrf": csrf, "target_level": "5", "timezone": "Asia/Jakarta", "exam_date": "", "role": "owner"},
        )
        await client.post("/mulai", data={"csrf": csrf, "nickname": "Licik", "target_level": "5", "role": "owner"})
        assert (await client.get("/admin/learners")).status_code == 404
    role = await scalar(engine_databases, "SELECT role FROM learning.learners WHERE public_id = :p", p=public_id)
    assert role == "learner"


async def test_only_set_role_makes_an_owner_and_it_is_audited(engine_databases: Databases) -> None:
    client, public_id = await signed_up(engine_databases, "Calon")
    async with aclosing(client):
        assert (await client.get("/admin/learners")).status_code == 404
        await owner.set_role(engine_databases.app, owner.COMMAND_LINE, public_id, "owner")
        page = await client.get("/admin/learners")
    assert page.status_code == 200 and public_id in page.text
    audit = await scalar(
        engine_databases, "SELECT detail FROM app.owner_actions WHERE action = 'set_role' AND subject = :p", p=public_id
    )
    assert audit == {"from": "learner", "to": "owner"}


async def test_the_owner_is_also_a_learner(engine_databases: Databases) -> None:
    client, public_id = await signed_up(engine_databases, "Pemilik")
    await owner.set_role(engine_databases.app, owner.COMMAND_LINE, public_id, "owner")
    async with aclosing(client):
        assert (await client.get("/beranda")).status_code == 200
        assert (await client.get("/kuis")).status_code == 200


async def make_owner(db: Databases, nickname: str) -> tuple[httpx.AsyncClient, str]:
    client, public_id = await signed_up(db, nickname)
    await owner.set_role(db.app, owner.COMMAND_LINE, public_id, "owner")
    return client, public_id


async def test_the_owner_issues_codes_from_the_page_and_each_is_audited(engine_databases: Databases) -> None:
    client, owner_id = await make_owner(engine_databases, "Pemberi")
    async with aclosing(client):
        page = await client.get("/admin/learners")
        issued = await client.post("/admin/learners/codes", data={"csrf": csrf_of(page), "count": "2"})
    codes = [line.split("<li>")[1] for line in issued.text.split("</li>") if "<li>" in line]
    assert issued.status_code == 200 and len(codes) == 2
    for code in codes:
        assert (await redeem(engine_databases.app, code)).learner_id is None
    detail = await scalar(
        engine_databases,
        "SELECT a.detail::text FROM app.owner_actions a JOIN learning.learners o ON o.id = a.owner_id "
        "WHERE o.public_id = :p AND a.action = 'issue_codes' AND a.place = 'page'",
        p=owner_id,
    )
    assert all(code.split(".")[0] in detail and code.split(".")[1] not in detail for code in codes)


async def test_the_owner_page_refuses_too_many_codes(engine_databases: Databases) -> None:
    client, owner_id = await make_owner(engine_databases, "Banyak")
    async with aclosing(client):
        page = await client.get("/admin/learners")
        refused = await client.post("/admin/learners/codes", data={"csrf": csrf_of(page), "count": "101"})
    assert refused.status_code == 400 and "ask for fewer" in refused.text
    assert await scalar(engine_databases, ACTIONS_BY, p=owner_id) == 0


async def test_the_owner_removes_a_learner_and_it_is_audited(engine_databases: Databases) -> None:
    other, other_id = await signed_up(engine_databases, "Pergi")
    await other.aclose()
    client, _ = await make_owner(engine_databases, "Penghapus")
    async with aclosing(client):
        page = await client.get("/admin/learners")
        removed = await client.post(
            "/admin/learners/remove", data={"csrf": csrf_of(page), "public_id": other_id, "confirm": other_id}
        )
    assert removed.status_code == 200 and f"Removed {other_id}" in removed.text
    assert await learners_with(engine_databases, other_id) == 0
    audited = await scalar(engine_databases, "SELECT count(*) FROM app.owner_actions WHERE subject = :p", p=other_id)
    assert audited == 1


async def test_removing_needs_the_public_id_typed_to_confirm(engine_databases: Databases) -> None:
    other, other_id = await signed_up(engine_databases, "Tetap")
    await other.aclose()
    client, _ = await make_owner(engine_databases, "Ragu")
    async with aclosing(client):
        page = await client.get("/admin/learners")
        refused = await client.post(
            "/admin/learners/remove", data={"csrf": csrf_of(page), "public_id": other_id, "confirm": "HAPUS"}
        )
    assert refused.status_code == 400
    assert await learners_with(engine_databases, other_id) == 1


async def test_an_owner_cannot_be_removed_until_made_a_learner(engine_databases: Databases) -> None:
    client, owner_id = await make_owner(engine_databases, "Tunggal")
    async with aclosing(client):
        page = await client.get("/admin/learners")
        refused = await client.post(
            "/admin/learners/remove", data={"csrf": csrf_of(page), "public_id": owner_id, "confirm": owner_id}
        )
    assert refused.status_code == 400 and "set-role" in refused.text
    with pytest.raises(owner.OwnerActionRefusedError):
        await owner.remove_learner(engine_databases.app, owner.COMMAND_LINE, owner_id)
    assert await learners_with(engine_databases, owner_id) == 1


async def test_removing_an_unknown_learner_says_so_and_changes_nothing(engine_databases: Databases) -> None:
    client, owner_id = await make_owner(engine_databases, "Salah")
    async with aclosing(client):
        page = await client.get("/admin/learners")
        refused = await client.post(
            "/admin/learners/remove", data={"csrf": csrf_of(page), "public_id": "no-such-id", "confirm": "no-such-id"}
        )
    assert refused.status_code == 400 and "no learner with public ID" in refused.text
    assert await scalar(engine_databases, ACTIONS_BY, p=owner_id) == 0


async def test_the_app_role_cannot_rewrite_the_audit(engine_databases: Databases) -> None:
    await owner.issue_codes(engine_databases.app, owner.COMMAND_LINE, 1)
    for statement in ("UPDATE app.owner_actions SET subject = 'x'", "DELETE FROM app.owner_actions"):
        async with engine_databases.app.connect() as connection:
            await connection.execute(text("SET ROLE juku_app"))
            with pytest.raises(ProgrammingError, match="permission denied"):
                await connection.execute(text(statement))
