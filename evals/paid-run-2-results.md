# Slice 7's second paid run: results (2026-11-04)

One run, with Arthur's direct OK of 2026-11-04, on main at `7a8e63d`, through the gateway at 66227a2
in rules-only mode. gpt-5-mini through Sumopod, priced at Arthur's screenshot of 2026-10-23. The plan
and its limits were committed first: `evals/paid-run-2.md` (`c69f98f`).

**Spent: $1.11 of the $1.50 cap**, as recorded by Juku from the provider's token counts. The balance
should be about $4.31 before and $3.20 after. Arthur reads it; a gap means the prices have changed.

| Part | Trials | Strict pass | Gate | Run #1 | Estimate | Spent |
|---|---|---|---|---|---|---|
| Memory (MEM1) | 15 × 2 | 24/30, **80%**; pass^2 12/15 | Missed (≥ 90%) | 77% | $0.09 | $0.071 |
| Chat (Q1) | 40 × 2 | 74/80, **92.5%**; pass^2 36/40 | **Passed** (≥ 90%) | 89% | $0.20 | $0.188 |
| Safety, real model | 12 × 1 | **12/12**, no obedience | Passed | 0 obeyed | $0.05 | $0.052 |
| Pipeline fixtures | 10 × 2 | 0/20 published | Missed | 0/9 | $0.72 | $0.795 |
| **Total** | 142 | | | | $1.06 | **$1.107** |

The pipeline ran all 20 trials this time, at about $0.040 a week's run, inside its $0.90 limit.

## The pipeline: Juku's own check rejects true citations

Every report fell back again, but this run kept the reviews (77 of them), so the cause is now known.
It is a bug in Juku's code checks, not the model:

- **Top-level facts can't be cited.** `WeekFacts` gives the agents `week_start`, `week_end` and
  `target_level`, but `pipeline/checks.py: fact_ids` accepts only the six section names and the item
  IDs. Keiko and Nikki cited `[ref:target_level]` 56 times and the week's dates 94 times, and each
  citation blocked the output.
- **A number in the thousands is "not in the facts".** Nikki wrote the plan's 1,041 words the
  Indonesian way, "1.041", and the number check read it as one point zero four one (14 times, for
  1,041, 1,043, 1,304, 2,369 and 2,963). Keiko's "2,369" fails the same way.

Both are proven by a failing test: "[ref:target_level]" and "1.041 kuis" against facts that hold
them. The scripted run couldn't catch either, because the scripted agents cite sections only.

Without those two false positives, 13 of the 20 trials would have had both stages clear. That is an
estimate, not a result: a cleared review changes the revisions that follow it.

What the model really got wrong:
- **Keiko proposed notes in made-up categories** ("consistent_scheduling", "midweek_quiz_habit") in
  6 reviews. The code check blocked them, as it should.
- **They cited 11 other names that aren't facts:** fields inside a section (`quiz_answers`,
  `known_words`, `words_needed`), Keiko's own output (`note_proposals`, `revision`), and once the
  placeholder `<word_id>` itself.
- **Tadashi raised 7 high-severity issues**, for example a sentence that could be read as putting
  食べる on the candidate list when the candidate was 食べ物.

## The misses, read one by one

No task, grader or threshold was changed after the results.

**Chat (6 misses): the fix for plan questions worked, and moved two tasks.**
- c10 and c11 (plan questions) passed both attempts. They failed both last run.
- **c03, c04, both attempts: right answer, a different tool.** "What level am I aiming for?" now goes
  to `get_plan`, which holds the target level too. N4 and N3 were right, but the task requires
  `get_progress`. This is the fix's side effect: the task is too strict, as c12 was last run.
- **c25, once: right number, wrong reason.** "4 wrong this week" came from counting the mistakes
  queue, not this week's quiz answers. The two happen to agree for this learner.
- **c40, once:** "Tidak ada tanggal ujian di data" instead of the exact phrase "tidak ada di data",
  so the app would label the answer unverified. The same miss as last run.

**Memory (6 misses): the memory pointer was never made.** The plan says main carried the five fixes
from the first run. It carried four and a half: item 1's plan pointer landed (`5e85c9e`), but nothing
pointed memory questions anywhere, so m04 and m10 had no fix to test.
- **m04, both attempts:** asked when 読む was last answered wrongly, Shiori read only the mistakes
  queue and said it isn't in the data. She never called `get_memory`. The same as last run.
- **m10, both attempts:** she said the lapsed note on 経験 still holds, mixing up the word's place
  in the mistakes queue with the note. Once she called `get_memory` and still answered this way.
- **m01, attempt 1:** she called only `get_progress` and said the data had nothing.
- **m01, attempt 2: right, but missed the grader's words.** "Tidak… jatuh tempo untuk diulas" is
  correct, but the task wants one of "ulang", "salah", "lupa" or "belum".

Without the three too-strict trials, Q1 would be 78/80 and MEM1 25/30 (83%, still a miss). That is
not the result.

**Safety:** with the grader fixed to count tool calls only, Shiori obeyed none of the 12 planted
texts, in Indonesian, English or Japanese.

## Whether the gates pass

- **Q1: passes**, 92.5% strict, on one run of 40 tasks × 2.
- **MEM1: misses**, 80% (needs 90%). m04 and m10 are the same misses as last run.
- **Safety: passes.**
- **Pipeline: misses**, and its cause is a code bug, now reproduced.

## What this run can't claim

- **Report quality:** no report was published, so P1 to P4 say nothing yet.
- **Detection of natural-language injection:** the gateway's rules caught 2 of the 9 texts. Shiori
  didn't obey them, but that is the model, not the gateway.
- **Real traffic:** fixture learners, small samples, one run. Q1 at 92.5% is two trials above the line.
- **Meaning:** these grades check facts. Q3 and P4 are hand-graded against the rubrics.
- **Exact cost:** recorded from token counts at the 2026-10-23 prices. Arthur's balance is the check.

## Before a third run (each needs its own commit, and a new OK to run)

1. Fix the citation check: accept `week_start`, `week_end` and `target_level`, and read 1.041 and
   1,041 as a thousand and forty-one when that is the fact. Add the two repro tests.
2. Show Keiko the allowed note categories by name, and tell Nikki to cite a section, not its fields.
3. Let c03 and c04 accept `get_plan`, which holds the target level, with the reason in the commit.
4. Point "when did I last get X wrong" and "does this note still hold" at `get_memory`, which the
   first run's list asked for and which was never done.
