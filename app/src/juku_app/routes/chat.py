"""Chat with Shiori (Phase 2 AG5, UI3): the history, the streamed answer, and ratings.

The answer streams as server-sent events: a `delta` per piece of text, then
one `done` with whether its citations checked out and the stored answer's ID.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from juku_app.chat import ChatAnswer, ask_streaming
from juku_app.routes.common import Page, header_csrf, page, render, web

CHAT_HISTORY = 20

router = APIRouter()


class ChatQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Rating(BaseModel):
    target_kind: Literal["chat", "report"]
    target_id: int
    is_helpful: bool
    reason: Literal["salah", "tidak_jelas", "tidak_relevan", "terlalu_panjang", "lainnya"] | None = None
    may_quote: bool = False


@router.get("/chat")
async def chat_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
    async with web(request).db.app.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT id, role, body, is_verified FROM app.chat_messages WHERE learner_id = :id "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {"id": current.learner.id, "limit": CHAT_HISTORY},
            )
        ).all()
    return render(request, "chat.html", page=current, messages=list(reversed(rows)))


@router.post("/chat/kirim", dependencies=[Depends(header_csrf)])
async def send(request: Request, question: ChatQuestion, current: Page = Depends(page)) -> EventSourceResponse:  # noqa: B008
    services = web(request).chat

    async def events() -> AsyncIterator[dict[str, str]]:
        async for piece in ask_streaming(services, current.learner, question.question, datetime.now(UTC)):
            if isinstance(piece, ChatAnswer):
                done = {
                    "is_verified": piece.is_verified,
                    "stopped_because": piece.stopped_because,
                    "message_id": piece.message_id,
                }
                yield {"event": "done", "data": json.dumps(done)}
            else:
                yield {"event": "delta", "data": piece}

    return EventSourceResponse(events())


@router.post("/nilai", dependencies=[Depends(header_csrf)], status_code=204)
async def rate(request: Request, rating: Rating, current: Page = Depends(page)) -> Response:  # noqa: B008
    async with web(request).db.app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.ratings (learner_id, target_kind, target_id, is_helpful, reason, may_quote) "
                "VALUES (:learner, :kind, :target, :helpful, :reason, :quote)"
            ),
            {
                "learner": current.learner.id,
                "kind": rating.target_kind,
                "target": rating.target_id,
                "helpful": rating.is_helpful,
                "reason": rating.reason,
                "quote": rating.may_quote,
            },
        )
    return Response(status_code=204)
