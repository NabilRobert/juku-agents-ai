"""Code's own high-severity checks on Keiko's plan and Nikki's report (ADR-007; Phase 2 AG1; Phase 1 P2, MEM4).

Tadashi checks too, but a model can miss a wrong number, and that is the
cheap thing to check in code. So whatever Tadashi says, an output is
blocked if:
- a number in it isn't in the facts (the week's dates, and digits stuck
  to letters such as "N5", aren't claims; "1.041" and "1,041" both
  count as 1,041, since Indonesian groups thousands with dots);
- it cites nothing, or cites something not in the facts (the facts'
  own fields, such as target_level, and the IDs of words and notes);
- it cites a note or a mistake that newer activity has since removed, or
  a note the learner removed, marked wrong, or saw lapse before the run
  (`retired`: never shown to agents, so a citation to one is stale memory,
  MEM4);
- a plan's word isn't one of the engine's candidates, or isn't at the
  level the plan says; a review word isn't in the mistakes queue;
- a plan proposes a note outside memory's allowed categories;
- the report is longer than the rule file allows.
Each issue is high severity, with its `kind` naming the check.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, cast

from juku_common.rules import Rules

from juku_app.pipeline.facts import WeekFacts
from juku_app.pipeline.outputs import Issue, KeikoPlan

# A number on its own, not part of a word ("N5", "2x"), with all its separators: "1.304.000" is one
# number, so it's checked whole rather than skipped.
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*(?![\w]|[.,]\d)")
SEPARATOR = re.compile(r"[.,]")
DIGITS_PER_THOUSANDS_GROUP = 3
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
CITATION = re.compile(r"\[ref:([^\]\s]+)\]")
PERCENT = 100


def _issue(kind: str, reason: str, quote: str = "") -> Issue:
    return Issue(quote=quote, reason=reason, severity="high", source="code", kind=kind)


def fact_ids(facts: WeekFacts) -> set[str]:
    """Everything a citation may name: the facts' own fields, the words and the notes."""
    # Agents see every top-level field (the sections, target_level, the week's dates), so each is
    # citable. Fields inside a section are not.
    ids = set(WeekFacts.model_fields)
    ids |= {word.word_id for word in facts.candidates.words}
    ids |= {item.word_id for item in facts.mistakes.items}
    ids |= {note.note_id for note in facts.memory.notes}
    return ids


def _leaves(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for child in cast(dict[str, Any], value).values():
            yield from _leaves(child)
    elif isinstance(value, list):
        for child in cast(list[Any], value):
            yield from _leaves(child)
    else:
        yield value


def fact_numbers(facts: WeekFacts) -> set[float]:
    """Every number the facts hold, and each share also as a percentage (one decimal at most)."""
    numbers: set[float] = set()
    for leaf in _leaves(facts.model_dump(mode="json")):
        if isinstance(leaf, bool) or not isinstance(leaf, int | float):
            continue
        numbers.add(float(leaf))
        if isinstance(leaf, float) and 0 <= leaf <= 1:
            numbers |= {float(round(leaf * PERCENT)), round(leaf * PERCENT, 1)}
    return numbers


def fact_dates(facts: WeekFacts) -> set[str]:
    return {
        leaf[:10] for leaf in _leaves(facts.model_dump(mode="json")) if isinstance(leaf, str) and ISO_DATE.match(leaf)
    }


def number_readings(written: str) -> set[float]:
    """What a written number can mean. Indonesian groups thousands with dots, English with commas.

    So "1.041" reads as both 1,041 and 1.041, "1.234,5" only as 1234.5, and "1.3.4" as nothing,
    which is never in the facts.
    """
    groups = SEPARATOR.split(written)
    separators = SEPARATOR.findall(written)
    if not separators:
        return {float(written)}
    readings: set[float] = set()
    is_grouped = len(set(separators)) == 1 and not groups[0].startswith("0")
    if is_grouped and all(len(group) == DIGITS_PER_THOUSANDS_GROUP for group in groups[1:]):
        readings.add(float("".join(groups)))
    if separators.count(separators[-1]) == 1:
        # The last separator appears once, so it can be the decimal mark, with any before it grouping thousands.
        readings.add(float("".join(groups[:-1]) + "." + groups[-1]))
    return readings


def _number_issues(text: str, facts: WeekFacts) -> list[Issue]:
    dates = fact_dates(facts)
    # A citation is an ID, not a claim, and an ID can be all digits; _citation_issues checks it against the facts.
    without_citations = CITATION.sub(" ", text)
    without_dates = ISO_DATE.sub(lambda found: " " if found.group(0) in dates else found.group(0), without_citations)
    allowed = fact_numbers(facts)
    return [
        _issue("number_not_in_facts", f"{number} isn't in the facts", number)
        for number in NUMBER.findall(without_dates)
        if not number_readings(number) & allowed
    ]


def _citation_issues(text: str, facts: WeekFacts, fresh: WeekFacts, retired: frozenset[str]) -> list[Issue]:
    cited = CITATION.findall(text)
    if not cited:
        return [_issue("missing_citation", "no fact is cited", text[:80])]
    known, current = fact_ids(facts), fact_ids(fresh)
    issues = [
        _issue("stale_claim", f"{ref} was taken back before this run", ref)
        if ref in retired
        else _issue("unknown_citation", f"{ref} isn't in the facts", ref)
        for ref in cited
        if ref not in known
    ]
    issues += [
        _issue("stale_claim", f"{ref} no longer holds: newer activity removed it", ref)
        for ref in cited
        if ref in known and ref not in current
    ]
    return issues


def _word_issues(plan: KeikoPlan, facts: WeekFacts) -> list[Issue]:
    candidates = {word.word_id: word for word in facts.candidates.words}
    mistakes = {item.word_id for item in facts.mistakes.items}
    issues: list[Issue] = []
    for word in plan.focus:
        candidate = candidates.get(word.word_id)
        if candidate is None:
            issues.append(_issue("word_not_a_candidate", f"{word.word_id} isn't one of the engine's candidates"))
        elif candidate.level != word.level:
            issues.append(_issue("off_level_word", f"{word.word_id} is N{candidate.level}, not N{word.level}"))
    issues += [
        _issue("word_not_in_mistakes", f"{word_id} isn't in the mistakes queue")
        for word_id in plan.review_word_ids
        if word_id not in mistakes
    ]
    return issues


def check_plan(
    plan: KeikoPlan, facts: WeekFacts, fresh: WeekFacts, rules: Rules, retired: frozenset[str] = frozenset()
) -> list[Issue]:
    issues = _word_issues(plan, facts)
    issues += [
        _issue("forbidden_note", f"a note in {proposal.category!r}, which isn't about learning")
        for proposal in plan.note_proposals
        if proposal.category not in rules.memory.allowed_categories
    ]
    return issues + _number_issues(plan.explanation, facts) + _citation_issues(plan.explanation, facts, fresh, retired)


def check_report(
    report: str, facts: WeekFacts, fresh: WeekFacts, rules: Rules, retired: frozenset[str] = frozenset()
) -> list[Issue]:
    issues: list[Issue] = []
    if len(report.split()) > rules.pipeline.report_max_words:
        issues.append(_issue("too_long", f"over {rules.pipeline.report_max_words} words"))
    return issues + _number_issues(report, facts) + _citation_issues(report, facts, fresh, retired)
