"""Studying words in context ($0, from the dictionary): a word's page, the grammar points, and a kanji.

Arthur, 2026-11-05: Juku drilled single words ("its just anki"). A word's page shows it in use, a grammar
point explains a sentence structure, and every example sentence can be explained word by word. A kanji
answers as JSON, for the pages to show its readings when it's hovered or tapped.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from juku_data import engine

from juku_app.routes.common import LEVELS, Page, page, render, web

router = APIRouter()


@router.get("/kata/{word_id}")
async def word_page(request: Request, word_id: str, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    db = web(request).db
    entry = await engine.get_word(db, current.learner.id, word_id)
    if entry is None:
        raise HTTPException(status_code=404)
    breakdowns = await engine.explain_sentences(db, current.learner.id, [example.ja for example in entry.examples])
    return render(request, "kata.html", page=current, entry=entry, breakdowns=breakdowns)


@router.get("/tata-bahasa")
async def grammar_list(request: Request, level: int | None = None, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    """A level's grammar points: the learner's target level unless they pick another of N5 to N2."""
    shown_level = level if level in LEVELS else current.learner.target_level
    points = await engine.get_grammar_at_level(web(request).db, shown_level)
    return render(request, "tata_bahasa.html", page=current, level=shown_level, levels=LEVELS, points=points)


@router.get("/tata-bahasa/{grammar_id}")
async def grammar_point(request: Request, grammar_id: str, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    db = web(request).db
    point = await engine.get_grammar_point(db, grammar_id)
    if point is None:
        raise HTTPException(status_code=404)
    breakdowns = await engine.explain_sentences(db, current.learner.id, [example.ja for example in point.examples])
    return render(request, "tata_bahasa_pola.html", page=current, point=point, breakdowns=breakdowns)


@router.get("/kanji/{kanji}")
async def kanji(request: Request, kanji: str, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    entry = await engine.get_kanji(web(request).db, current.learner.id, kanji) if len(kanji) == 1 else None
    if entry is None:
        return JSONResponse({"error": "not_a_jlpt_kanji"}, status_code=404)
    return JSONResponse(entry.model_dump(mode="json"))
