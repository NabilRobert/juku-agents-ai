"""The home page's "I know this word" without a reload (routes/learning.py: mark_recommended_known)."""

from juku_app.invites import issue_codes
from juku_data.engine import Databases
from web_helpers import client_for, csrf_header, deps, page_props, sign_up


async def test_marking_a_recommendation_returns_the_count_and_the_next_words(engine_databases: Databases) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases)) as client:
        await sign_up(client, code)
        home = await client.get("/beranda")
        first = page_props(home)["words"][0]["word_id"]
        marked = await client.post(f"/rekomendasi/{first}/dikuasai", headers=csrf_header(home))
        unknown = await client.post("/rekomendasi/no-such-word/dikuasai", headers=csrf_header(home))
        without_token = await client.post(f"/rekomendasi/{first}/dikuasai")
    assert marked.status_code == 200
    assert marked.json()["known_words"] == 1
    assert first not in [word["word_id"] for word in marked.json()["words"]]
    assert unknown.status_code == 404
    assert without_token.status_code == 403
