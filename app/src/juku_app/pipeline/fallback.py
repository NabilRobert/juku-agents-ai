"""The facts-only report, from a template (ADR-007; Phase 1 P3): what a learner gets when no output passes.

Built from the facts alone, in Indonesian, so it holds no claim code can't
check: every number is a fact, every sentence cites its section.
"""

from __future__ import annotations

from juku_app.pipeline.facts import WeekFacts

# The candidates named, at most: enough to act on, short enough to read.
WORDS_NAMED = 3


def facts_only_report(facts: WeekFacts) -> str:
    activity = facts.activity
    lines = [
        f"Laporan {facts.week_start.isoformat()} sampai {facts.week_end.isoformat()}.",
        f"Minggu ini kamu menjawab {activity.quiz_answers} kuis ({activity.quiz_correct} benar), "
        f"menandai {activity.words_marked} kata, dan membaca {activity.sentences_read} kalimat [ref:activity].",
        f"Sekarang kamu menguasai {facts.progress.known_words} kata [ref:progress].",
    ]
    if facts.mistakes.items:
        words = ", ".join(item.word for item in facts.mistakes.items[:WORDS_NAMED])
        lines.append(f"Kata yang perlu diulang: {words} [ref:mistakes].")
    if facts.candidates.words:
        words = ", ".join(word.word for word in facts.candidates.words[:WORDS_NAMED])
        lines.append(f"Kata baru yang disarankan: {words} [ref:candidates].")
    return " ".join(lines)
