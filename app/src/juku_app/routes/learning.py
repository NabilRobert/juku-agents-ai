"""The $0 learning pages (Phase 2 UI1): home and recommendations, the quiz, reading practice and the plan.

They call the learning engine directly; no model is involved.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from juku_data import engine
from juku_data.engine import UnknownWordError
from pydantic import BaseModel, Field

from juku_app.routes.common import Page, form_csrf, header_csrf, page, render, web

# Enough batches for a long session; a client can't ask for an unbounded slice.
MAX_QUIZ_BATCH = 20

router = APIRouter()


class QuizAnswer(BaseModel):
    word_id: str = Field(max_length=64)
    kind: Literal["meaning", "reading"]
    chosen: str = Field(max_length=500)


@router.get("/beranda")
async def home(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    db = web(request).db
    progress = await engine.get_progress(db, current.learner.id)
    recommendations = await engine.recommend_words(db, current.learner.id)
    return render(request, "beranda.html", page=current, progress=progress, words=recommendations.words)


@router.post("/kata/{word_id}/dikuasai", dependencies=[Depends(form_csrf)])
async def mark_known(request: Request, word_id: str, current: Page = Depends(page)) -> Response:  # noqa: B008
    try:
        await engine.mark_known(web(request).db, current.learner.id, word_id, datetime.now(UTC))
    except UnknownWordError:
        return HTMLResponse("Kata tidak dikenal.", status_code=404)
    return RedirectResponse("/beranda", status_code=303)


@router.get("/kuis")
async def quiz(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    made = await engine.make_quiz(web(request).db, current.learner.id, current.today)
    return render(request, "kuis.html", page=current, quiz_json=made.model_dump_json())


@router.get("/kuis/data")
async def quiz_batch(request: Request, batch: int = 0, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    """The next ten questions, for the quiz island to fetch before it runs out (FE6)."""
    batch = max(0, min(batch, MAX_QUIZ_BATCH))
    made = await engine.make_quiz(web(request).db, current.learner.id, current.today, batch=batch)
    return JSONResponse(made.model_dump(mode="json"))


@router.post("/kuis/jawab", dependencies=[Depends(header_csrf)])
async def answer_quiz(request: Request, answer: QuizAnswer, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
    try:
        graded = await engine.grade_answer(
            web(request).db, current.learner.id, answer.word_id, answer.kind, answer.chosen, datetime.now(UTC)
        )
    except UnknownWordError:
        return JSONResponse({"error": "unknown_word"}, status_code=404)
    return JSONResponse(graded.model_dump(mode="json"))


@router.get("/bacaan")
async def reading(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    sentences = await engine.find_reading_sentences(web(request).db, current.learner.id)
    return render(request, "bacaan.html", page=current, sentences=sentences.sentences)


@router.post("/bacaan/{sentence_id}/dibaca", dependencies=[Depends(form_csrf)])
async def sentence_read(request: Request, sentence_id: int, current: Page = Depends(page)) -> Response:  # noqa: B008
    await engine.record_sentence_read(web(request).db, current.learner.id, sentence_id, datetime.now(UTC))
    return RedirectResponse("/bacaan", status_code=303)


@router.get("/rencana")
async def plan(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    db = web(request).db
    progress = await engine.get_progress(db, current.learner.id)
    made = await engine.get_plan(db, current.learner.id, current.today)
    return render(request, "rencana.html", page=current, progress=progress, plan=made)
