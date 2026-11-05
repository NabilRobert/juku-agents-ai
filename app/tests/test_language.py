"""The ID | EN switch (routes/site.py: choose_language; i18n.use_language)."""

import httpx
import pytest
from juku_app.invites import issue_codes
from juku_app.routes.site import same_site_path
from juku_data.engine import Databases
from web_helpers import client_for, csrf_of, deps, page_props, shell_props, sign_up


async def switch(client: httpx.AsyncClient, language: str, back: str = "/beranda") -> httpx.Response:
    page = await client.get("/masuk")
    return await client.post("/bahasa", data={"csrf": csrf_of(page), "language": language, "back": back})


async def test_a_learner_switches_the_pages_to_english_and_back(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        switched = await switch(client, "en", back="/kuis")
        english = await client.get("/beranda")
        await switch(client, "id")
        indonesian = await client.get("/beranda")
    assert switched.status_code == 303 and switched.headers["location"] == "/kuis"
    assert '<html lang="en">' in english.text and page_props(english)["copy"]["hello"] == "Hello"
    assert shell_props(english)["sections"][0]["label"] == "Home"
    assert '<html lang="id">' in indonesian.text and page_props(indonesian)["copy"]["hello"] == "Halo"


async def test_the_switch_works_before_signing_in(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await switch(client, "en", back="/masuk")
        page = await client.get("/masuk")
    assert page_props(page)["copy"]["welcome"] == "Welcome to Juku"


async def test_one_learners_language_never_reaches_another(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as english, client_for(deps(engine_databases)) as other:
        await switch(english, "en", back="/masuk")
        assert page_props(await english.get("/masuk"))["copy"]["welcome"] == "Welcome to Juku"
        assert page_props(await other.get("/masuk"))["copy"]["welcome"] == "Selamat datang di Juku"


async def test_an_unknown_language_leaves_the_pages_as_they_were(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await switch(client, "fr", back="/masuk")
        page = await client.get("/masuk")
    assert '<html lang="id">' in page.text


async def test_switching_needs_the_pages_csrf_token(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        refused = await client.post("/bahasa", data={"language": "en", "back": "/masuk"})
        page = await client.get("/masuk")
    assert refused.status_code == 403
    assert '<html lang="id">' in page.text


@pytest.mark.parametrize(
    "back",
    [
        "//evil.example/x",
        "https://evil.example/",
        "/\\evil.example",
        "javascript:alert(1)",
        "/beranda\r\nSet-Cookie: x",
    ],
)
def test_the_switch_returns_only_to_a_page_on_this_site(back: str) -> None:
    assert same_site_path(back) == "/beranda"


def test_the_switch_returns_to_the_page_it_came_from() -> None:
    assert same_site_path("/tata-bahasa?level=4") == "/tata-bahasa?level=4"
