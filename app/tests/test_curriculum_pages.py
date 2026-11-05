"""The curriculum's pages (routes/curriculum.py): the path, a unit, marking things done, the placement test."""

import httpx
from juku_app.invites import issue_codes
from juku_data.engine import Databases
from web_helpers import client_for, csrf_header, deps, page_props, sign_up


async def signed_in(db: Databases, client: httpx.AsyncClient) -> None:
    code = (await issue_codes(db.app, 1))[0]
    await sign_up(client, code)


async def test_home_shows_todays_lesson_from_the_first_unit(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        today = page_props(await client.get("/beranda"))["today"]
    assert today["unit"]["unit_id"] == 1 and today["new_words"]


async def test_the_plan_page_shows_the_path_to_the_learners_target(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        curriculum = page_props(await client.get("/rencana"))["curriculum"]
    assert curriculum["current_unit_id"] == 1 and curriculum["levels"][0]["level"] == 5


async def test_marking_a_units_word_grammar_and_sentence_shows_on_its_page(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        page = await client.get("/rencana/unit/1")
        detail = page_props(page)["detail"]
        word, point = detail["words"][0]["word_id"], detail["grammar"][0]["grammar_id"]
        marked = [
            await client.post(f"/rencana/kata/{word}/dikuasai", headers=csrf_header(page)),
            await client.post(f"/rencana/tata-bahasa/{point}/paham", headers=csrf_header(page)),
        ]
        after = page_props(await client.get("/rencana/unit/1"))["detail"]["unit"]
    assert [response.status_code for response in marked] == [200, 200]
    assert after["words_known"] == 1 and after["grammar_studied"] == 1


async def test_marking_needs_the_token_and_a_real_item(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        page = await client.get("/rencana/unit/1")
        without_token = await client.post("/rencana/tata-bahasa/x/paham")
        unknown_point = await client.post("/rencana/tata-bahasa/no-such-point/paham", headers=csrf_header(page))
        unknown_word = await client.post("/rencana/kata/no-such-word/dikuasai", headers=csrf_header(page))
    assert (without_token.status_code, unknown_point.status_code, unknown_word.status_code) == (403, 404, 404)


async def test_a_unit_past_the_path_is_not_found(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        response = await client.get("/rencana/unit/99999")
    assert response.status_code == 404


async def test_placement_answers_all_wrong_leave_the_learner_at_the_start(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        page = await client.get("/rencana/penempatan?level=5")
        questions = page_props(page)["questions"]
        answers = [{"word_id": item["word_id"], "kind": item["kind"], "chosen": ""} for item in questions]
        placed = await client.post("/rencana/penempatan/5", json={"answers": answers}, headers=csrf_header(page))
        too_many = await client.post("/rencana/penempatan/5", json={"answers": answers * 2}, headers=csrf_header(page))
        unknown_level = await client.post("/rencana/penempatan/9", json={"answers": []}, headers=csrf_header(page))
    assert placed.json()["placed_through_unit_id"] == 0 and not placed.json()["passed_level"]
    assert (too_many.status_code, unknown_level.status_code) == (422, 404)


async def test_placement_never_offers_a_level_beyond_the_target(engine_databases: Databases) -> None:
    async with client_for(deps(engine_databases)) as client:
        await signed_in(engine_databases, client)
        props = page_props(await client.get("/rencana/penempatan?level=1"))
    assert props["level"] == 5
