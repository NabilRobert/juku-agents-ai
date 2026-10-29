""" "Shiori ingat..." (MEM-R5): every note with its evidence and age, the known words, and the learner's corrections."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from juku_data import engine
from juku_data.engine import Databases, UnknownWordError
from juku_data.engine.models import Learner
from juku_data.memory import NoteNotFoundError, get_memory, mark_note_wrong, remove_note

from juku_app.routes.common import Page, header_csrf, page, render, web

# get_memory names notes `note-<id>`, so Shiori can cite them; the page's URLs use the same.
NOTE_PREFIX = "note-"
# remove_note or mark_note_wrong: the learner's two corrections to a note.
NoteCorrection = Callable[[Databases, int, int, datetime], Awaitable[None]]

router = APIRouter()


@router.get("/ingat")
async def memory_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    """ "Shiori ingat..." (MEM-R5): every note with its evidence and age, and the words the learner knows."""
    db = web(request).db
    remembered = await get_memory(db, current.learner.id, datetime.now(UTC))
    known = await engine.get_known_words(db, current.learner.id)
    memory_data = {
        "notes": [note.model_dump(mode="json") for note in remembered.notes],
        "words": [word.model_dump(mode="json") for word in known.items],
    }
    return render(request, "ingat.html", page=current, memory_data=memory_data, known_total=known.total)


async def correct_note(db: Databases, note_ref: str, learner: Learner, correction: NoteCorrection) -> Response:
    """Apply the learner's correction to their own note; any other note is simply not found."""
    number = note_ref.removeprefix(NOTE_PREFIX)
    if not number.isdigit():
        return Response(status_code=404)
    try:
        await correction(db, learner.id, int(number), datetime.now(UTC))
    except NoteNotFoundError:
        return Response(status_code=404)
    return Response(status_code=204)


@router.post("/ingat/catatan/{note_ref}/hapus", dependencies=[Depends(header_csrf)])
async def remove(request: Request, note_ref: str, current: Page = Depends(page)) -> Response:  # noqa: B008
    return await correct_note(web(request).db, note_ref, current.learner, remove_note)


@router.post("/ingat/catatan/{note_ref}/salah", dependencies=[Depends(header_csrf)])
async def mark_wrong(request: Request, note_ref: str, current: Page = Depends(page)) -> Response:  # noqa: B008
    return await correct_note(web(request).db, note_ref, current.learner, mark_note_wrong)


@router.post("/ingat/kata/{word_id}/belum", dependencies=[Depends(header_csrf)])
async def unmark(request: Request, word_id: str, current: Page = Depends(page)) -> Response:  # noqa: B008
    """Unmark a known word (MEM-R5): known again only by marking it or answering right on two days."""
    try:
        await engine.unmark_known(web(request).db, current.learner.id, word_id, datetime.now(UTC))
    except UnknownWordError:
        return Response(status_code=404)
    return Response(status_code=204)
