"""Static copies of the pages, for Lighthouse CI (fitness function FF12).

Lighthouse measures what a phone downloads and how fast the page paints.
The pages need a database and a session, which CI's browser doesn't have,
so this renders each page's template with sample data into plain HTML
files, with the built islands beside them, and Lighthouse runs on those.
The HTML, the islands and the stylesheet are the real ones.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from juku_data.engine.curriculum_models import (
    CurriculumLevel,
    CurriculumOverview,
    TodayPlan,
    UnitGrammar,
    UnitStatus,
    UnitWord,
    WeekDay,
)
from juku_data.engine.models import (
    KnownWord,
    Learner,
    LevelCoverage,
    Plan,
    Progress,
    Quiz,
    QuizItem,
    ReadingSentence,
    RecommendedWord,
)
from juku_data.memory import EvidenceEvent, MemoryNote

from juku_app import assets
from juku_app.activity import CALENDAR_WEEKS, ActiveDay
from juku_app.routes.common import LEVELS, TIMEZONES, templates

SAMPLE_LEARNER = Learner(
    id=0, public_id="preview", cohort_id=1, target_level=5, timezone="Asia/Jakarta", exam_date=date(2026, 12, 6)
)


@dataclass(frozen=True)
class SamplePage:
    learner: Learner
    nickname: str
    today: date
    is_owner: bool = False


def sample_activity(today: date) -> list[ActiveDay]:
    """A few weeks of practice ending today, busier on weekends, for the home page's calendar."""
    days: list[ActiveDay] = []
    for back in range(0, 40, 2):
        count = 3 + (back % 7) * 2
        day = today - timedelta(days=back)
        days.append(
            ActiveDay(day=day, count=count, quiz_answers=count - 1, words_marked=1, sentences_read=0, questions=0)
        )
    return sorted(days, key=lambda active: active.day)


def sample_memory() -> dict[str, Any]:
    """One note with its evidence and a few known words, shaped as the memory page renders them."""
    evidence = [
        EvidenceEvent(
            event_id=number,
            event_type="quiz_reading",
            word_id="w1",
            word="読む",
            reading="よむ",
            level=5,
            is_correct=False,
            occurred_on=date(2026, 10, 28 + number),
        )
        for number in range(3)
    ]
    note = MemoryNote(
        note_id="note-1",
        category="recurring_confusion",
        text="Sering salah membaca 読む.",
        evidence=evidence,
        noted_on=date(2026, 10, 31),
        last_evidence_on=date(2026, 10, 30),
        age_days=1,
    )
    words = [KnownWord(word_id=f"k{number}", word="水", reading="みず") for number in range(10)]
    return {"notes": [note.model_dump(mode="json")], "words": [word.model_dump(mode="json") for word in words]}


def sample_unit(number: int, status: str) -> UnitStatus:
    words_known = {"done": 15, "current": 6, "later": 0}[status]
    return UnitStatus.model_validate(
        {
            "unit_id": number,
            "level": 5,
            "number": number,
            "words_total": 15,
            "words_known": words_known,
            "grammar_total": 2,
            "grammar_studied": 2 if status == "done" else 0,
            "sentences_total": 5,
            "sentences_read": 5 if status == "done" else 0,
            "status": status,
        }
    )


def sample_curriculum() -> dict[str, Any]:
    """N5's 45 units, two done and one under way, and today's lesson from the third: the plan page and Home."""
    units = [
        sample_unit(number, "done" if number < 3 else "current" if number == 3 else "later") for number in range(1, 46)
    ]
    curriculum = CurriculumOverview(
        target_level=5, units_total=45, units_done=2, current_unit_id=3, levels=[CurriculumLevel(level=5, units=units)]
    )
    new_words = [
        UnitWord(word_id=f"u{number}", word="水", reading="みず", meanings=["water"], is_known=False)
        for number in range(9)
    ]
    today = TodayPlan(
        unit=units[2],
        new_words=new_words,
        words_target=10,
        words_done=1,
        grammar=UnitGrammar(grammar_id="g1", pattern="は", meaning="topic marker", is_studied=False),
        grammar_done=0,
        sentences=[],
        sentences_target=3,
        sentences_done=0,
        reviews_due=4,
        quiz_target=10,
        quiz_done=0,
        week=[
            WeekDay(day=date(2026, 11, 2) + timedelta(days=offset), done=done, target=24, is_future=offset > 3)
            for offset, done in enumerate([24, 13, 0, 1, 0, 0, 0])
        ],
    )
    note = {"week_start": "2026-10-26", "body": "Kamu di unit 3, dan 2 dari 45 unit N5 sudah selesai [ref:curriculum]."}
    return {"curriculum": curriculum, "today": today, "keiko_note": note, "is_check_queued": False}


def sample_context() -> dict[str, Any]:
    levels = [
        LevelCoverage(
            level=level,
            level_name=f"N{level}",
            words_known=known,
            words_total=total,
            kanji_known=kanji,
            kanji_total=kanji_total,
            word_coverage=known / total,
            kanji_coverage=kanji / kanji_total,
        )
        for level, known, total, kanji, kanji_total in ((5, 120, 674, 40, 103), (4, 10, 630, 2, 181))
    ]
    words = [
        RecommendedWord(
            word_id=f"w{number}",
            word="一つ",
            reading="ひとつ",
            level=5,
            meanings=["one"],
            new_kanji="一",
            leverage=9,
            reason="1 kanji baru: 一, muncul di 9 kata N5.",
        )
        for number in range(10)
    ]
    quiz = Quiz(
        items=[
            QuizItem(
                word_id=f"q{number}", kind="meaning", prompt="食べる", options=["to eat", "to drink", "to see", "to go"]
            )
            for number in range(10)
        ]
    )
    sentences = [
        ReadingSentence(
            sentence_id=number,
            ja="水を飲む。",
            furigana="{水|みず}を{飲|の}む。",
            en="I drink water.",
            tatoeba_id=1000 + number,
            new_word_id="w1",
            new_word="飲む",
        )
        for number in range(10)
    ]
    plan = Plan(
        target_level=5,
        target_coverage=0.8,
        words_in_scope=674,
        words_known=130,
        words_needed=410,
        exam_date=date(2026, 12, 6),
        weeks_left=5,
        words_per_week=82,
        formula="kata per minggu = (80% x 674 - 130) / 5",
    )
    return {
        "csrf": "preview",
        "page": SamplePage(SAMPLE_LEARNER, "Ayu", date(2026, 11, 1)),
        "progress": Progress(target_level=5, known_words=130, levels=levels),
        "words": words,
        "quiz": quiz,
        "sentences": sentences,
        "breakdowns": {},  # explanations come from the dict database, which previews don't use
        "active_days": sample_activity(date(2026, 11, 1)),
        "calendar_weeks": CALENDAR_WEEKS,
        "plan": plan,
        "messages": [],
        "memory_data": sample_memory(),
        "known_total": 130,
        "timezones": TIMEZONES,
        "levels": LEVELS,
    } | sample_curriculum()


PAGES = ("beranda", "kuis", "bacaan", "rencana", "chat", "ingat", "pengaturan", "tentang_data")


def render_previews(out: Path) -> list[Path]:
    """Write each page and the built islands under `out`, laid out as the app serves them."""
    environment = templates().env
    context = sample_context()
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in PAGES:
        html = environment.get_template(f"{name}.html").render(page_name=name, **context)
        path = out / f"{name}.html"
        path.write_text(html, encoding="utf-8")
        written.append(path)
    if (assets.STATIC / "dist").is_dir():
        shutil.copytree(assets.STATIC / "dist", out / "static" / "dist", dirs_exist_ok=True)
    return written
