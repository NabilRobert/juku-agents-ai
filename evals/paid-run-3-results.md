# Slice 7's third paid run: results (2026-11-05)

One run, with Arthur's direct OK of 2026-11-05, on main at `e217244`, through the gateway at 66227a2
in rules-only mode. gpt-5-mini through Sumopod, priced at Arthur's screenshot of 2026-10-23. The plan
and its limits were committed first: `evals/paid-run-3.md` (`82eb8a3`). A scripted run of all four
parts passed first ($0).

**Spent: $0.89 of the $1.50 cap**, as recorded by Juku from the provider's token counts. The balance
should be about $3.20 before and $2.31 after. Arthur reads it; a gap means the prices have changed.

| Part | Trials | Strict pass | Gate | Run #2 | Estimate | Spent |
|---|---|---|---|---|---|---|
| Memory (MEM1) | 15 × 2 | 28/30, **93.3%**; pass^2 13/15 | **Passed** (≥ 90%) | 80% | $0.07 | $0.075 |
| Chat (Q1) | 40 × 2 | 76/80, **95%**; pass^2 37/40 | **Passed** (≥ 90%) | 92.5% | $0.19 | $0.187 |
| Safety, real model | 12 × 1 | **12/12**, no obedience | Passed | 12/12 | $0.05 | $0.053 |
| Pipeline fixtures | 10 × 2 | 19/20 published; pass^2 9/10 | Missed (all 20) | 0/20 | $0.80 | $0.577 |
| **Total** | 142 | | | | $1.11 | **$0.892** |

The pipeline cost less than run 2 ($0.029 a week's run, against $0.040), because most drafts were
approved on the first or second review instead of being sent back until the limit.

## The pipeline: 19 of 20 published

The citation fix (#37) and the writers' instructions (#40) worked: run 2 published nothing. Of the 50
reviews, 38 approved the draft. The code check sent back one draft (Keiko cited `revision`, which the
instructions forbid), and Tadashi sent back 11.

**The one fallback (indra, attempt 1) kept no reason.** No review was recorded and no tool was called,
for $0.010. So Keiko's first draft never reached the check: either PydanticAI gave up on her output
after its retries, or the run hit its limit of 8 requests. The pipeline doesn't record which
(`pipeline/run.py: _reviewed` returns None on `UnexpectedModelBehavior`, and `run_weekly` catches
`BudgetSpentError`, both without a record). Attempt 2 for the same learner published.

**Tadashi reads citations as unfinished placeholders.** In 9 of his 11 send-backs, his main high
issue is that `[ref:week_start]`, `[ref:target_level]` or `[ref:<word_id>]` "was not replaced with
the real value". The writers are told to cite that way (`CITATION_RULE`), and the app shows the
citations, but `TADASHI_INSTRUCTIONS` only says a missing citation is high. It never says what a
citation looks like. Each of these trials published after a revision, so no report was lost, but
they cost a revision each and teach the writers the wrong lesson.

What Tadashi caught that was real:
- **joko, attempt 2:** Keiko called 大きい a wrong word. It is a valid i-adjective and a candidate.
- **nur, attempt 1, and oka, attempt 2:** Keiko's note proposals gave `evidence_event_ids` such as
  `[0, 1, 2, 3, 4]` and `[1, 4]`, which aren't in what she was given.

**Suspected, not yet reproduced: Keiko can't name real evidence.** `WeekFacts.activity` gives counts
per day, with no event IDs, and Keiko called no tool in any of the 20 trials. Her instructions still
ask for "ID aktivitas sebagai bukti", and the memory store refuses a note whose evidence it can't
find (`juku_data/memory/store.py`, rule 5). If that holds, no note Keiko proposes can be accepted. It
needs a failing test before it counts.

P1 to P4 (report quality) are hand-graded against the rubrics, and that grading hasn't been done yet.

## The misses, read one by one

No task, grader or threshold was changed after the results.

**Memory (2 misses): the `get_memory` pointer (#38) worked on one attempt of each.**
- m04 and m10 failed both attempts in runs 1 and 2. Each passed once this time, with `get_memory`.
- **m04, attempt 2:** asked when 読む was last answered wrongly, Shiori called only `get_mistakes`
  and said it isn't in the data. The same miss as before, half as often.
- **m10, attempt 2:** she called `get_memory`, which doesn't show the lapsed note, and answered
  "Tidak ada di data". That's true of what she was shown, but the task wants her to say the note no
  longer holds. Attempt 1 said "catatan itu tidak berlaku", from the same tool result.

**Chat (4 misses): c03 and c04, as named in the plan, and c40 again.**
- **c03, attempt 1, and c04, attempt 1: right answer, a different tool.** N4 and N3 from `get_plan`,
  but the task requires `get_progress`. The plan named these in advance. c03's attempt 2 used
  `get_progress` and passed.
- **c04, attempt 2: a wrong answer.** "JLPT level 3" from `get_plan` (which stores the level as 3),
  not "N3". The grader is right to fail it: the learner would read "level 3" as N3 only by guessing.
- **c40, attempt 1:** "Tidak ada tanggal ujian yang tercatat di data" instead of the exact phrase
  "tidak ada di data". The same miss as in runs 1 and 2, once each time.

Without the two too-strict trials (c03 #1 and c04 #1), Q1 would be 78/80. That is not the result.

**Safety:** Shiori obeyed none of the 12 planted texts, in Indonesian, English or Japanese.

## Whether the gates pass

- **Q1: passes**, 95% strict, on one run of 40 tasks × 2. Run 2 passed too, at 92.5%.
- **MEM1: passes**, 93.3% strict, for the first time. That is one trial above the line, on 15 tasks.
- **Safety: passes.**
- **Pipeline: misses**, 19 of 20 published. The one fallback's cause wasn't recorded.

## What this run can't claim

- **Report quality:** 19 reports were published, but P1 to P4 haven't been graded yet.
- **Detection of natural-language injection:** the gateway's rules caught 2 of the 9 texts. Shiori
  didn't obey them, but that is the model, not the gateway.
- **Real traffic:** fixture learners, small samples, one run. MEM1 at 93.3% is one trial above the
  line, and Q1 at 95% is two.
- **Meaning:** these grades check facts. Q3 and P4 are hand-graded against the rubrics.
- **Exact cost:** recorded from token counts at the 2026-10-23 prices. Arthur's balance is the check.

## Before a fourth run (each needs its own commit, and a new OK to run)

1. Record why a run fell back without a review (Keiko's output refused, or the request limit hit),
   so the next fallback can be read like the others.
2. Tell Tadashi what a citation looks like, and that the app shows it, so `[ref:...]` isn't a high issue.
3. Write the failing test for Keiko's evidence IDs. If it fails, give her the week's event IDs or
   stop asking her for them.
4. Let c03 and c04 accept `get_plan`, once the harness's any-of form is merged.
5. Grade P1 to P4 on the 19 published reports by hand.
