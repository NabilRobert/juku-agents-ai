# Rubric: hand-grading chat answers (Q3)

Each week Arthur grades a random sample of 20 answers. The target is at least
85%, so 17 of 20. The tasks in `suite.yaml` check facts automatically. This
rubric covers what code can't judge: whether a learner would understand the
answer.

An answer passes only if it meets both points. Grade what the learner saw.

| Point | Pass | Fail |
|---|---|---|
| **Correct** | Every fact is right and comes from the turn's tools. If the data doesn't have it, the answer says so. | A wrong fact, a guess, or a claim with no source, even if it sounds right. |
| **Well explained in Indonesian** | Natural, simple Indonesian that a beginner can follow, and it answers the question asked. Japanese comes with its reading when that helps. | Stiff or machine-like wording, too long, or correct but not what was asked. |

**How to grade:**
- An answer labelled "belum terverifikasi" can still pass, if it's correct. The
  label is a separate measure (Q2).
- A fixed reply (the budget, a run limit, a failed turn, distress) isn't
  sampled. These aren't Shiori's own words.
- For each fail, write one line saying why. Anything seen 3 or more times
  becomes a task or a fixture (`docs/planning/standard-checks.md`).
