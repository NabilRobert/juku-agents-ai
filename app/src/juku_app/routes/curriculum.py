"""The curriculum's pages (2026-11-05): the path on the plan page, a unit, the placement test.

Arthur: "is it possible to make a curriculum? ... since i picked n2 as my target. theres no structure."
The plan page shows the whole path, N5 to the learner's target, as numbered units; a unit's page holds its
words, kanji, grammar points and sentences. Marking one done posts JSON and changes nothing else on the
page. The placement test places a learner who already knows some further along. All $0.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from juku_data import engine
from juku_data.engine import PlacementAnswer, UnknownGrammarError, UnknownWordError
from pydantic import BaseModel, Field

from juku_app.routes.common import LEVELS, Page, header_csrf, page, render, web

# A placement test is one level's questions (engine/placement.py: PLACEMENT_QUESTIONS); a few spare.
MAX_PLACEMENT_ANSWERS = 20

router = APIRouter()


class PlacementAnswerIn(BaseModel):
    word_id: str = Field(max_length=64)
    kind: Literal["meaning", "reading"]
    chosen: str = Field(max_length=500)


class PlacementAnswers(BaseModel):
    answers: list[PlacementAnswerIn] = Field(max_length=MAX_PLACEMENT_ANSWERS)


@router.get("/rencana")
async def plan(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    db = web(request).db
    progress = await engine.get_progress(db, current.learner.id)
    made = await engine.get_plan(db, current.learner.id, current.today)
    curriculum = await engine.get_curriculum(db, current.learner.id)
    return render(request, "rencana.html", page=current, progress=progress, plan=made, curriculum=curriculum)


@router.get("/rencana/unit/{unit_id}")
async def unit(request: Request, unit_id: int, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    db = web(request).db
    found = await engine.get_unit(db, current.learner.id, unit_id)
    if found is None:
        raise HTTPException(status_code=404)
    breakdowns = await engine.explain_sentences(db, current.learner.id, [item.ja for item in found.sentences])
    return render(request, "rencana_unit.html", page=current, unit=found, breakdowns=breakdowns)


@router.post("/rencana/kata/{word_id}/dikuasai", dependencies=[Depends(header_csrf)])
async def word_known(request: Request, word_id: str, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    try:
        await engine.mark_known(web(request).db, current.learner.id, word_id, datetime.now(UTC))
    except UnknownWordError:
        return JSONResponse({"error": "unknown_word"}, status_code=404)
    return JSONResponse({"done": True})


@router.post("/rencana/tata-bahasa/{grammar_id}/paham", dependencies=[Depends(header_csrf)])
async def grammar_understood(request: Request, grammar_id: str, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    try:
        await engine.mark_grammar_studied(web(request).db, current.learner.id, grammar_id, datetime.now(UTC))
    except UnknownGrammarError:
        return JSONResponse({"error": "unknown_grammar"}, status_code=404)
    return JSONResponse({"done": True})


@router.post("/rencana/kalimat/{sentence_id}/dibaca", dependencies=[Depends(header_csrf)])
async def sentence_read(request: Request, sentence_id: int, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    await engine.record_sentence_read(web(request).db, current.learner.id, sentence_id, datetime.now(UTC))
    return JSONResponse({"done": True})


@router.get("/rencana/penempatan")
async def placement(request: Request, level: int = 5, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    """One level's placement questions; N5 first, then each level up to the learner's target."""
    shown_level = level if level in LEVELS and level >= current.learner.target_level else 5
    questions = await engine.get_placement_questions(web(request).db, current.learner.id, shown_level)
    return render(
        request,
        "rencana_penempatan.html",
        page=current,
        level=shown_level,
        questions=questions,
        next_level=shown_level - 1 if shown_level > current.learner.target_level else None,
    )


@router.post("/rencana/penempatan/{level}", dependencies=[Depends(header_csrf)])
async def place(request: Request, level: int, sent: PlacementAnswers, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    if level not in LEVELS:
        return JSONResponse({"error": "unknown_level"}, status_code=404)
    answers = [PlacementAnswer(word_id=item.word_id, kind=item.kind, chosen=item.chosen) for item in sent.answers]
    result = await engine.place_learner(web(request).db, current.learner.id, level, answers, datetime.now(UTC))
    return JSONResponse(result.model_dump(mode="json"))
