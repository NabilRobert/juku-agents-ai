"""The pages (UI1, FE1): the first visit, consent before anything, the $0 pages, chat, export and deletion."""

import json
import re
from pathlib import Path

import pytest
from juku_app.invites import issue_codes
from juku_data.engine import Databases
from sqlalchemy import text
from web_helpers import client_for, csrf_header, csrf_of, deps, found, sign_up

pytestmark = pytest.mark.xfail(strict=True, reason="EDD: the web app lands in the next commit")

TEMPLATES = Path(__file__).resolve().parents[1] / "src" / "juku_app" / "templates"
CATALOGUE = Path(__file__).resolve().parents[1] / "src" / "juku_app" / "locale" / "id" / "LC_MESSAGES" / "messages.po"


async def test_a_visitor_without_a_session_is_sent_to_sign_in(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        response = await client.get("/beranda")
    assert (response.status_code, response.headers["location"]) == (303, "/masuk")


async def test_a_wrong_code_is_refused_in_indonesian(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        page = await client.get("/masuk")
        response = await client.post("/masuk", data={"code": "salah.kode", "csrf": csrf_of(page)})
    assert response.status_code == 200
    assert "Kode tidak dikenal" in response.text


async def test_a_form_without_its_csrf_token_is_refused(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        response = await client.post("/masuk", data={"code": "x.y"})
    assert response.status_code == 403


async def test_the_first_visit_signs_up_and_lands_on_the_home_page(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        response = await sign_up(client, code)
        assert (response.status_code, response.headers["location"]) == (303, "/beranda")
        home = await client.get("/beranda")
    assert home.status_code == 200
    assert "Rekomendasi" in home.text
    assert "Ayu" in home.text


async def test_consent_says_18_and_processing_abroad(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        page = await client.get("/masuk")
        await client.post("/masuk", data={"code": code, "csrf": csrf_of(page)})
        consent = await client.get("/persetujuan")
    assert "18 tahun" in consent.text
    assert "di luar Indonesia" in consent.text


async def test_without_the_18_tick_there_is_no_account(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        page = await client.get("/masuk")
        await client.post("/masuk", data={"code": code, "csrf": csrf_of(page)})
        page = await client.get("/persetujuan")
        response = await client.post("/persetujuan", data={"accepts_service": "on", "csrf": csrf_of(page)})
        assert response.status_code == 200
        assert "18 tahun" in response.text
        assert (await client.get("/mulai")).status_code == 303


async def test_a_returning_learner_signs_in_with_the_same_code(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Budi")
    async with client_for(deps(engine_databases)) as fresh:
        page = await fresh.get("/masuk")
        response = await fresh.post("/masuk", data={"code": code, "csrf": csrf_of(page)})
        assert response.headers["location"] == "/beranda"
        assert "Budi" in (await fresh.get("/beranda")).text


@pytest.mark.parametrize("path", ["/beranda", "/kuis", "/bacaan", "/rencana", "/chat", "/pengaturan", "/tentang-data"])
async def test_each_page_renders_for_a_signed_in_learner(engine_databases: Databases, path: str) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        response = await client.get(path)
    assert response.status_code == 200, response.text[:300]
    assert '<html lang="id">' in response.text


async def test_reading_practice_uses_ruby_for_furigana(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        page = await client.get("/bacaan")
    assert "<ruby>" in page.text


async def test_a_quiz_answer_is_graded_and_recorded(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        page = await client.get("/kuis")
        quiz = json.loads(found(r'<script type="application/json" id="quiz-data">(.*?)</script>', page.text))
        item = quiz["items"][0]
        response = await client.post(
            "/kuis/jawab",
            json={"word_id": item["word_id"], "kind": item["kind"], "chosen": item["options"][0]},
            headers=csrf_header(page),
        )
    assert response.status_code == 200
    assert set(response.json()) >= {"is_correct", "correct_option"}


async def test_marking_a_word_known_is_the_learners_own_click(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        home = await client.get("/beranda")
        word_id = found(r'data-word-id="([^"]+)"', home.text)
        response = await client.post(f"/kata/{word_id}/dikuasai", data={"csrf": csrf_of(home)})
        assert response.status_code == 303
        progress = await client.get("/rencana")
    assert "1 kata" in progress.text


async def test_chat_streams_an_answer_as_server_sent_events(engine_databases: Databases, juku_mcp_url: str) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases, juku_mcp_url)) as client:
        await sign_up(client, code)
        page = await client.get("/chat")
        response = await client.post("/chat/kirim", json={"question": "apa itu 食べる?"}, headers=csrf_header(page))
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in response.text
    assert "event: done" in response.text
    assert "tidak ada di data" in response.text


async def test_a_rating_is_stored(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        page = await client.get("/chat")
        response = await client.post(
            "/nilai",
            json={"target_kind": "chat", "target_id": 1, "is_helpful": False, "reason": "salah", "may_quote": False},
            headers=csrf_header(page),
        )
    assert response.status_code == 204


async def test_the_export_is_a_json_download_of_the_learners_data(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Citra")
        response = await client.get("/unduh-data")
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.json()["learner"]["nickname"] == "Citra"


async def test_deleting_my_data_ends_the_session_and_mentions_the_backup_tail(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code, nickname="Dewi")
        settings = await client.get("/pengaturan")
        response = await client.post("/hapus-data", data={"confirm": "HAPUS", "csrf": csrf_of(settings)})
        assert response.status_code == 200
        assert "7 hari" in response.text
        assert (await client.get("/beranda")).status_code == 303
    async with engine_databases.app.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM learning.learners WHERE nickname = 'Dewi'")) == 0


async def test_web_vitals_are_stored_without_a_learner(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        response = await client.post("/web-vitals", json={"page": "beranda", "metric": "LCP", "value": 1.2})
    assert response.status_code == 204


async def test_the_health_check_answers(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        assert (await client.get("/healthz")).json() == {"status": "ok"}


def test_every_phrase_in_the_templates_has_an_indonesian_translation() -> None:
    from babel.messages.pofile import read_po

    with CATALOGUE.open("rb") as file:
        catalogue = read_po(file, locale="id")
    used = {
        phrase
        for template in TEMPLATES.rglob("*.html")
        for phrase in re.findall(r'_\("([^"]+)"\)', template.read_text(encoding="utf-8"))
    }
    assert used, "no phrases found: the templates should use _()"
    translated = {str(message.id) for message in catalogue if message.id and message.string}
    missing = sorted(used - translated)
    assert missing == []
