"""The web app (Phase 2 UI1-UI3, FE1): server-rendered pages in Indonesian, with Vue islands where interactive.

A learner's first visit: an invite code (/masuk), the consent notice
(/persetujuan), then their nickname, level, timezone and exam date
(/mulai). After that, every page needs a signed-in learner whose consent
is on the current version; anything else is redirected.

The $0 pages call the learning engine directly; only chat calls a model,
through Shiori and the budget guard. Every form carries a CSRF token
tied to the session; the islands send it in a header. The browser holds
no model or MCP key (UI2): it talks only to this app.
"""

from __future__ import annotations

import json
import re
import secrets
import time
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import structlog
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data import engine
from juku_data.engine import Databases, LearnerNotFoundError, UnknownWordError
from juku_data.engine.models import Learner
from juku_data.memory import NoteNotFoundError, get_memory, mark_note_wrong, remove_note
from pydantic import BaseModel, Field
from pydantic_ai.models import Model
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.sessions import SessionMiddleware

from juku_app import assets, i18n, privacy
from juku_app.budget import BudgetGuard
from juku_app.chat import ChatAnswer, ChatServices, ask_streaming
from juku_app.consent import CONSENT_VERSION, ConsentAnswers, ConsentRefusedError, has_current_consent, record_consent
from juku_app.invites import Invite, InviteRefusedError, attach, redeem
from juku_app.moderation import Moderator
from juku_app.ruby import furigana_to_ruby
from juku_app.shiori import build_shiori, juku_toolset

HERE = Path(__file__).parent
SESSION_DAYS = 30
CHAT_HISTORY = 20
DELETE_CONFIRMATION = "HAPUS"
TIMEZONES = ("Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura", "Asia/Tokyo")
LEVELS = (5, 4, 3, 2)
# Enough batches for a long session; a client can't ask for an unbounded slice.
MAX_QUIZ_BATCH = 20
# The Run Inspector's lists: enough to see the week, small enough to load at once.
INSPECTOR_ROWS = 50
CITATION_MARKER = re.compile(r"\s*\[ref:[^\]\s]+\]")
LATEST_RUNS = """
SELECT r.id, l.public_id, r.week_start, r.kind, r.status, r.attempts, r.started_at, r.finished_at
FROM app.pipeline_runs r JOIN learning.learners l ON l.id = r.learner_id ORDER BY r.id DESC LIMIT :limit
"""
LATEST_DRAFTS = (
    "SELECT week_start, agent, patterns, draft, status FROM app.prompt_feedback ORDER BY id DESC LIMIT :limit"
)
ONE_RUN = """
SELECT r.id, l.public_id, r.week_start, r.kind, r.status, r.attempts, r.started_at, r.finished_at, r.facts
FROM app.pipeline_runs r JOIN learning.learners l ON l.id = r.learner_id WHERE r.id = :id
"""
RUN_ATTEMPTS = """
SELECT o.agent, o.attempt, o.content, c.grade, c.issues, c.code_issues, c.is_approved, c.reason
FROM app.agent_outputs o JOIN app.critic_reviews c ON c.output_id = o.id WHERE o.run_id = :id ORDER BY o.id
"""
RUN_REPORT = "SELECT body, is_fallback FROM app.reports WHERE run_id = :id"
# get_memory names notes `note-<id>`, so Shiori can cite them; the page's URLs use the same.
NOTE_PREFIX = "note-"
# remove_note or mark_note_wrong: the learner's two corrections to a note.
NoteCorrection = Callable[[Databases, int, int, datetime], Awaitable[None]]


@dataclass(frozen=True)
class WebDeps:
    db: Databases
    rules: Rules
    signer: Signer
    session_secret: str
    model: Model
    juku_mcp_url: str
    shiori_gateway_key: str | None
    moderator: Moderator
    crisis_line: str
    secure_cookies: bool = True
    # Who may open the Run Inspector (AG3): Arthur's own public ID, from the settings.
    admin_public_ids: frozenset[str] = frozenset()


@dataclass
class Redirect(Exception):
    """Raised by a dependency to send the visitor elsewhere (303)."""

    location: str


@dataclass(frozen=True)
class Page:
    """What every learner page gets: the learner, their nickname, and their local date."""

    learner: Learner
    nickname: str
    today: date = field(default_factory=date.today)


class QuizAnswer(BaseModel):
    word_id: str = Field(max_length=64)
    kind: Literal["meaning", "reading"]
    chosen: str = Field(max_length=500)


class ChatQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class Rating(BaseModel):
    target_kind: Literal["chat", "report"]
    target_id: int
    is_helpful: bool
    reason: Literal["salah", "tidak_jelas", "tidak_relevan", "terlalu_panjang", "lainnya"] | None = None
    may_quote: bool = False


class WebVital(BaseModel):
    page: str = Field(max_length=40, pattern=r"^[a-z-]+$")
    metric: Literal["LCP", "INP", "CLS"]
    value: float = Field(ge=0, le=600_000)


def templates() -> Jinja2Templates:
    environment = Jinja2Templates(directory=HERE / "templates")
    environment.env.add_extension("jinja2.ext.i18n")
    environment.env.install_gettext_callables(i18n.gettext, i18n.ngettext, newstyle=True)  # type: ignore[attr-defined]
    helpers = cast(dict[str, Any], environment.env.globals)  # pyright: ignore[reportUnknownMemberType]
    helpers.update(island=assets.island, stylesheet=assets.stylesheet, ruby=furigana_to_ruby)
    return environment


def csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not isinstance(token, str):
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token


def check_csrf(request: Request, sent: str | None) -> None:
    expected = request.session.get("csrf")
    if not isinstance(expected, str) or not sent or not secrets.compare_digest(expected, sent):
        raise Redirect("/csrf")


async def form_csrf(request: Request, csrf: str = Form("")) -> None:
    check_csrf(request, csrf)


async def header_csrf(request: Request) -> None:
    check_csrf(request, request.headers.get("X-CSRF-Token"))


def create_web_app(deps: WebDeps) -> FastAPI:  # noqa: C901, PLR0915 (32 routes as closures; the split into APIRouters waits on Arthur's OK)
    db = deps.db
    guard = BudgetGuard(db.app, deps.rules)
    chat = ChatServices(
        agent=build_shiori(deps.model, juku_toolset(deps.juku_mcp_url, deps.shiori_gateway_key)),
        guard=guard,
        moderator=deps.moderator,
        signer=deps.signer,
        app=db.app,
        crisis_line=deps.crisis_line,
    )
    views = templates()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        await guard.sync_pool_sizes()
        yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        SessionMiddleware,
        secret_key=deps.session_secret,
        session_cookie="juku_session",
        max_age=SESSION_DAYS * 24 * 3600,
        same_site="lax",
        https_only=deps.secure_cookies,
    )
    app.mount("/static", StaticFiles(directory=assets.STATIC, check_dir=False), name="static")
    log = structlog.get_logger("juku_app")

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """One line per request: method, route, status and time. Never a body, a query or a form."""
        started = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        log.info(
            "request",
            method=request.method,
            route=getattr(route, "path", "unmatched"),
            status=response.status_code,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response

    @app.exception_handler(Redirect)
    async def redirect(_: Request, exception: Redirect) -> Response:
        if exception.location == "/csrf":
            return HTMLResponse("Formulir kedaluwarsa. Muat ulang halaman, lalu coba lagi.", status_code=403)
        return RedirectResponse(exception.location, status_code=303)

    def render(request: Request, name: str, **context: Any) -> HTMLResponse:
        # The page's name, for real-user timings (FE8): "beranda" for /beranda.
        page_name = request.url.path.strip("/").split("/")[0] or "root"
        return views.TemplateResponse(request, name, {"csrf": csrf_token(request), "page_name": page_name, **context})

    async def nickname_of(learner: Learner) -> str:
        async with db.app.connect() as connection:
            return str(
                await connection.scalar(
                    text("SELECT nickname FROM learning.learners WHERE id = :id"), {"id": learner.id}
                )
            )

    async def signed_in(request: Request) -> Learner:
        public_id = request.session.get("learner")
        if not isinstance(public_id, str):
            raise Redirect("/masuk")
        try:
            return await engine.get_learner(db, public_id)
        except LearnerNotFoundError:
            request.session.clear()
            raise Redirect("/masuk") from None

    async def page(learner: Learner = Depends(signed_in)) -> Page:  # noqa: B008 (FastAPI's dependency idiom)
        """A learner page: signed in, and consent on the current version (no activity without it)."""
        if not await has_current_consent(db.app, learner.id):
            raise Redirect("/persetujuan")
        today = datetime.now(UTC).astimezone(ZoneInfo(learner.timezone)).date()
        return Page(learner=learner, nickname=await nickname_of(learner), today=today)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def root() -> Response:
        return RedirectResponse("/beranda", status_code=303)

    @app.get("/masuk")
    async def sign_in_form(request: Request) -> HTMLResponse:
        return render(request, "masuk.html")

    @app.post("/masuk", dependencies=[Depends(form_csrf)])
    async def sign_in(request: Request, code: str = Form("")) -> Response:
        try:
            invite = await redeem(db.app, code)
        except InviteRefusedError:
            return render(request, "masuk.html", error=True)
        if invite.learner_id is None:
            request.session["invite"] = invite.id
            return RedirectResponse("/persetujuan", status_code=303)
        async with db.app.connect() as connection:
            public_id = await connection.scalar(
                text("SELECT public_id FROM learning.learners WHERE id = :id"), {"id": invite.learner_id}
            )
        request.session["learner"] = str(public_id)
        location = "/beranda" if await has_current_consent(db.app, invite.learner_id) else "/persetujuan"
        return RedirectResponse(location, status_code=303)

    def pending_invite(request: Request) -> int | None:
        value = request.session.get("invite")
        return value if isinstance(value, int) else None

    @app.get("/persetujuan")
    async def consent_form(request: Request) -> Response:
        if pending_invite(request) is None and "learner" not in request.session:
            raise Redirect("/masuk")
        return render(request, "persetujuan.html", version=CONSENT_VERSION)

    @app.post("/persetujuan", dependencies=[Depends(form_csrf)])
    async def consent(
        request: Request,
        is_adult: str = Form(""),
        accepts_service: str = Form(""),
        accepts_aggregates: str = Form(""),
        accepts_group_digest: str = Form(""),
    ) -> Response:
        answers = ConsentAnswers(
            is_adult=bool(is_adult),
            accepts_service=bool(accepts_service),
            accepts_aggregates=bool(accepts_aggregates),
            accepts_group_digest=bool(accepts_group_digest),
        )
        if not (answers.is_adult and answers.accepts_service):
            return render(request, "persetujuan.html", version=CONSENT_VERSION, error=True)
        public_id = request.session.get("learner")
        if isinstance(public_id, str):  # a returning learner, asked again for a new version
            learner = await engine.get_learner(db, public_id)
            await record_consent(db.app, learner.id, answers)
            return RedirectResponse("/beranda", status_code=303)
        if pending_invite(request) is None:
            raise Redirect("/masuk")
        request.session["consent"] = answers.__dict__
        return RedirectResponse("/mulai", status_code=303)

    @app.get("/mulai")
    async def start_form(request: Request) -> Response:
        if pending_invite(request) is None or "consent" not in request.session:
            raise Redirect("/masuk")
        return render(request, "mulai.html", timezones=TIMEZONES, levels=LEVELS)

    @app.post("/mulai", dependencies=[Depends(form_csrf)])
    async def start(
        request: Request,
        nickname: str = Form(..., min_length=1, max_length=30),
        target_level: int = Form(5),
        timezone: str = Form("Asia/Jakarta"),
        exam_date: str = Form(""),
    ) -> Response:
        invite_id, answers = pending_invite(request), request.session.get("consent")
        if invite_id is None or not isinstance(answers, dict):
            raise Redirect("/masuk")
        learner = await engine.create_learner(
            db,
            nickname=nickname.strip(),
            target_level=target_level,
            timezone=timezone,
            exam_date=date.fromisoformat(exam_date) if exam_date else None,
        )
        await attach(db.app, Invite(id=invite_id, learner_id=None), learner.id)
        try:
            await record_consent(db.app, learner.id, ConsentAnswers(**cast(dict[str, bool], answers)))
        except ConsentRefusedError:
            raise Redirect("/persetujuan") from None
        request.session.pop("invite", None)
        request.session.pop("consent", None)
        request.session["learner"] = learner.public_id
        return RedirectResponse("/beranda", status_code=303)

    @app.get("/beranda")
    async def home(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        progress = await engine.get_progress(db, current.learner.id)
        recommendations = await engine.recommend_words(db, current.learner.id)
        return render(request, "beranda.html", page=current, progress=progress, words=recommendations.words)

    @app.post("/kata/{word_id}/dikuasai", dependencies=[Depends(form_csrf)])
    async def mark_known(word_id: str, current: Page = Depends(page)) -> Response:  # noqa: B008
        try:
            await engine.mark_known(db, current.learner.id, word_id, datetime.now(UTC))
        except UnknownWordError:
            return HTMLResponse("Kata tidak dikenal.", status_code=404)
        return RedirectResponse("/beranda", status_code=303)

    @app.get("/kuis")
    async def quiz(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        made = await engine.make_quiz(db, current.learner.id, current.today)
        return render(request, "kuis.html", page=current, quiz_json=made.model_dump_json())

    @app.get("/kuis/data")
    async def quiz_batch(batch: int = 0, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
        """The next ten questions, for the quiz island to fetch before it runs out (FE6)."""
        made = await engine.make_quiz(db, current.learner.id, current.today, batch=max(0, min(batch, MAX_QUIZ_BATCH)))
        return JSONResponse(made.model_dump(mode="json"))

    @app.post("/kuis/jawab", dependencies=[Depends(header_csrf)])
    async def answer_quiz(answer: QuizAnswer, current: Page = Depends(page)) -> JSONResponse:  # noqa: B008
        try:
            graded = await engine.grade_answer(
                db, current.learner.id, answer.word_id, answer.kind, answer.chosen, datetime.now(UTC)
            )
        except UnknownWordError:
            return JSONResponse({"error": "unknown_word"}, status_code=404)
        return JSONResponse(graded.model_dump(mode="json"))

    @app.get("/bacaan")
    async def reading(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        sentences = await engine.find_reading_sentences(db, current.learner.id)
        return render(request, "bacaan.html", page=current, sentences=sentences.sentences)

    @app.post("/bacaan/{sentence_id}/dibaca", dependencies=[Depends(form_csrf)])
    async def sentence_read(sentence_id: int, current: Page = Depends(page)) -> Response:  # noqa: B008
        await engine.record_sentence_read(db, current.learner.id, sentence_id, datetime.now(UTC))
        return RedirectResponse("/bacaan", status_code=303)

    @app.get("/rencana")
    async def plan(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        progress = await engine.get_progress(db, current.learner.id)
        made = await engine.get_plan(db, current.learner.id, current.today)
        return render(request, "rencana.html", page=current, progress=progress, plan=made)

    @app.get("/chat")
    async def chat_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        async with db.app.connect() as connection:
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

    @app.post("/chat/kirim", dependencies=[Depends(header_csrf)])
    async def send(question: ChatQuestion, current: Page = Depends(page)) -> EventSourceResponse:  # noqa: B008
        async def events() -> AsyncIterator[dict[str, str]]:
            async for piece in ask_streaming(chat, current.learner, question.question, datetime.now(UTC)):
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

    @app.post("/nilai", dependencies=[Depends(header_csrf)], status_code=204)
    async def rate(rating: Rating, current: Page = Depends(page)) -> Response:  # noqa: B008
        async with db.app.begin() as connection:
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

    @app.get("/ingat")
    async def memory_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        """ "Shiori ingat..." (MEM-R5): every note with its evidence and age, and the words the learner knows."""
        remembered = await get_memory(db, current.learner.id, datetime.now(UTC))
        known = await engine.get_known_words(db, current.learner.id)
        memory_data = {
            "notes": [note.model_dump(mode="json") for note in remembered.notes],
            "words": [word.model_dump(mode="json") for word in known.items],
        }
        return render(request, "ingat.html", page=current, memory_data=memory_data, known_total=known.total)

    async def correct_note(note_ref: str, learner: Learner, correction: NoteCorrection) -> Response:
        """Apply the learner's correction to their own note; any other note is simply not found."""
        number = note_ref.removeprefix(NOTE_PREFIX)
        if not number.isdigit():
            return Response(status_code=404)
        try:
            await correction(db, learner.id, int(number), datetime.now(UTC))
        except NoteNotFoundError:
            return Response(status_code=404)
        return Response(status_code=204)

    @app.post("/ingat/catatan/{note_ref}/hapus", dependencies=[Depends(header_csrf)])
    async def remove(note_ref: str, current: Page = Depends(page)) -> Response:  # noqa: B008
        return await correct_note(note_ref, current.learner, remove_note)

    @app.post("/ingat/catatan/{note_ref}/salah", dependencies=[Depends(header_csrf)])
    async def mark_wrong(note_ref: str, current: Page = Depends(page)) -> Response:  # noqa: B008
        return await correct_note(note_ref, current.learner, mark_note_wrong)

    @app.post("/ingat/kata/{word_id}/belum", dependencies=[Depends(header_csrf)])
    async def unmark(word_id: str, current: Page = Depends(page)) -> Response:  # noqa: B008
        """Unmark a known word (MEM-R5): known again only by marking it or answering right on two days."""
        try:
            await engine.unmark_known(db, current.learner.id, word_id, datetime.now(UTC))
        except UnknownWordError:
            return Response(status_code=404)
        return Response(status_code=204)

    @app.get("/laporan")
    async def report_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        """The learner's latest weekly report (AG1), with the citation markers kept out of their way."""
        async with db.app.connect() as connection:
            latest = (
                await connection.execute(
                    text(
                        "SELECT week_start, body, is_fallback FROM app.reports WHERE learner_id = :id "
                        "ORDER BY week_start DESC LIMIT 1"
                    ),
                    {"id": current.learner.id},
                )
            ).first()
        report = None
        if latest is not None:
            report = {"week_start": latest.week_start, "body": CITATION_MARKER.sub("", str(latest.body)).strip()}
        return render(request, "laporan.html", page=current, report=report)

    async def admin(learner: Learner = Depends(signed_in)) -> Learner:  # noqa: B008
        """Arthur only: anyone else gets the same 404 as a page that doesn't exist."""
        if learner.public_id not in deps.admin_public_ids:
            raise HTTPException(status_code=404)
        return learner

    @app.get("/admin/runs", dependencies=[Depends(admin)])
    async def admin_runs(request: Request) -> HTMLResponse:
        """The Run Inspector's index (AG3): the latest runs, and the feedback job's drafts (AG4)."""
        async with db.app.connect() as connection:
            runs = (await connection.execute(text(LATEST_RUNS), {"limit": INSPECTOR_ROWS})).mappings().all()
            drafts = (await connection.execute(text(LATEST_DRAFTS), {"limit": INSPECTOR_ROWS})).mappings().all()
        return views.TemplateResponse(request, "admin_runs.html", {"runs": runs, "drafts": drafts})

    @app.get("/admin/runs/{run_id}", dependencies=[Depends(admin)])
    async def admin_run(request: Request, run_id: int) -> HTMLResponse:
        """One run: its facts, every draft, every review with code's issues, the decision, the report."""
        async with db.app.connect() as connection:
            run = (await connection.execute(text(ONE_RUN), {"id": run_id})).mappings().first()
            if run is None:
                raise HTTPException(status_code=404)
            attempts = (await connection.execute(text(RUN_ATTEMPTS), {"id": run_id})).mappings().all()
            report = (await connection.execute(text(RUN_REPORT), {"id": run_id})).mappings().first()
        context = {"run": run, "facts": json.dumps(run["facts"], ensure_ascii=False, indent=1), "attempts": attempts}
        return views.TemplateResponse(request, "admin_run.html", {**context, "report": report})

    @app.get("/pengaturan")
    async def settings_page(request: Request, current: Page = Depends(page)) -> HTMLResponse:  # noqa: B008
        return render(request, "pengaturan.html", page=current, timezones=TIMEZONES, levels=LEVELS)

    @app.post("/pengaturan", dependencies=[Depends(form_csrf)])
    async def update_settings(
        current: Page = Depends(page),  # noqa: B008
        target_level: int = Form(...),
        timezone: str = Form(...),
        exam_date: str = Form(""),
    ) -> Response:
        if target_level != current.learner.target_level:
            await engine.set_target_level(db, current.learner.id, target_level)
        if timezone != current.learner.timezone:
            await engine.set_timezone(db, current.learner.id, timezone)
        async with db.app.begin() as connection:
            await connection.execute(
                text("UPDATE learning.learners SET exam_date = :exam WHERE id = :id"),
                {"exam": date.fromisoformat(exam_date) if exam_date else None, "id": current.learner.id},
            )
        return RedirectResponse("/pengaturan", status_code=303)

    @app.get("/unduh-data")
    async def download(current: Page = Depends(page)) -> Response:  # noqa: B008
        exported = await privacy.export_learner(db.app, current.learner.id)
        return Response(
            json.dumps(exported, ensure_ascii=False, indent=1),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="juku-data-saya.json"'},
        )

    @app.post("/hapus-data", dependencies=[Depends(form_csrf)])
    async def delete(request: Request, current: Page = Depends(page), confirm: str = Form("")) -> Response:  # noqa: B008
        if confirm.strip().upper() != DELETE_CONFIRMATION:
            return render(
                request, "pengaturan.html", page=current, timezones=TIMEZONES, levels=LEVELS, delete_error=True
            )
        await privacy.delete_learner(db.app, current.learner.id)
        request.session.clear()
        return render(request, "hapus_selesai.html")

    @app.get("/tentang-data")
    async def about_the_data(request: Request) -> HTMLResponse:
        return render(request, "tentang_data.html")

    @app.post("/web-vitals", status_code=204)
    async def web_vitals(vital: WebVital) -> Response:
        async with db.app.begin() as connection:
            await connection.execute(
                text("INSERT INTO app.web_vitals (page, metric, value) VALUES (:page, :metric, :value)"),
                {"page": vital.page, "metric": vital.metric, "value": vital.value},
            )
        return Response(status_code=204)

    return app
