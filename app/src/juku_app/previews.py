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
from datetime import date
from pathlib import Path
from typing import Any

from juku_data.engine.models import (
    Learner,
    LevelCoverage,
    Plan,
    Progress,
    Quiz,
    QuizItem,
    ReadingSentence,
    RecommendedWord,
)

from juku_app import assets
from juku_app.web import LEVELS, TIMEZONES, templates

SAMPLE_LEARNER = Learner(
    id=0, public_id="preview", cohort_id=1, target_level=5, timezone="Asia/Jakarta", exam_date=date(2026, 12, 6)
)


@dataclass(frozen=True)
class SamplePage:
    learner: Learner
    nickname: str
    today: date


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
        "quiz_json": quiz.model_dump_json(),
        "sentences": sentences,
        "plan": plan,
        "messages": [],
        "timezones": TIMEZONES,
        "levels": LEVELS,
    }


PAGES = ("beranda", "kuis", "bacaan", "rencana", "chat", "pengaturan", "tentang_data")


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
