# Spike 4: how cleanly do the JLPT lists and Tatoeba's index map to JMdict?

**Plan change (2026-10-28):** Juku's data is now OpenJLPT (ADR-003), so the
question became **"how complete is OpenJLPT for Juku?"** That's answered
first. The original mapping of Waller's lists and Tatoeba's index to JMdict
follows, and it now records **what Juku would face without OpenJLPT**.

## How complete is OpenJLPT? (the plan)

**Pass: counted, with rules.** At the pinned commit `bf4e1ee` (see spike
1):
- **11 of 7,811 words have no JMdict link (0.1%),** all of them phrases
  or rare spellings (お待ちください, 一段と, 矢鱈に…);
- **all 7,800 links resolve** in JMdict_e 2026-10-28;
- **566 words (7.2%) have no example,** 400 of them at N1 and 115 at N2;
- **90.7% of the content tokens** in its 12,615 distinct example
  sentences map to one OpenJLPT word ID;
- **63.3% of sentences map completely** (66.1% if ない counts as grammar).

```
python openjlpt/completeness.py data/raw/openjlpt-main/openjlpt.sqlite > openjlpt/results.md
```

It needs spike 1's `dict` database and spike 4's `jlpt_map`, for the
cross-checks. [openjlpt/results.md](4-jlpt-mapping/results/openjlpt/results.md) is the full
output; `openjlpt/compare.sh` reproduces the cross-checks against Waller's
lists ([openjlpt/results-compare.txt](4-jlpt-mapping/results/openjlpt/results-compare.txt)). It takes about 2 s.

- **OpenJLPT is Waller's lists, with better JMdict links.**
  - Where both have the same (spelling, reading), 7,553 of 7,561 IDs
    agree (99.9%) with this spike's rule-based mapping. Two of the 8
    differences are mistakes in the rules here (いえ, 何 なん). The rest
    are homographs worth a look (撃つ うつ, ソース, ポーズ).
  - The 94 reference IDs with no OpenJLPT word are mostly the
    reference's wrong homographs (これ, それ, 私, だんだん): OpenJLPT has
    those words, with the right IDs.
  - 120 entries sit at a different level than in the reference list.
- **The i+1 check:** example sentences were tokenized with SudachiPy 0.7.0
  (sudachidict-core 20260723.1), split mode C. Each token was matched by
  lemma:
  1. OpenJLPT's spelling or other forms;
  2. Sudachi's normalized form;
  3. the reading, for a kana lemma;
  4. otherwise its finer mode-A units (私たち → 私), for compounds
     OpenJLPT doesn't list.

  Homographs were narrowed by the lemma's reading. Particles, auxiliaries,
  affixes and symbols were left out (LE4's function words); names and
  numbers count as known.

| Content tokens | 62,609 |
|---|---|
| One word ID | 56,784 (90.7%) |
| Several IDs (homographs: よう, つい, おい…) | 773 (1.2%) |
| No OpenJLPT word | 5,052 (8.1%) |

- **The unmatched words are a real gap:** 父, 母, 顔, 多く, 人々, 夕食,
  野球, ドル. These are common words that **neither Waller's lists nor
  OpenJLPT include** (spike 4's lists don't have them either). ない
  (and its forms) is grammar in OpenJLPT, not vocabulary.
- **Hand check, a sample of 30 mapped tokens:** 29 right, 1 doubtful
  (日にち → 日日, glossed "every day").

### Rules proposed for slice 2

1. Match example tokens by lemma, in the order above, keeping the lemma's
   reading to narrow homographs. A token that is still ambiguous makes its
   sentence ineligible, never a guess.
2. Count function words, names and numbers as known. Count ない and its
   forms, and OpenJLPT's grammar patterns, as grammar, not vocabulary.
3. Common words outside the lists (父, 母, 顔…): a small reviewed
   supplement file (with JMdict IDs), marked "outside the JLPT list", so
   that i+1 sentences can use them. Or leave them unmatched, so the
   sentence doesn't qualify. The supplement is the recommendation.
4. The 11 unlinked words keep OpenJLPT's stable ID, which is what Juku
   stores. Only a future JMdict import would need them mapped, so the
   count is reported, and no fix is needed now.
5. The 566 words with no example get none in reading practice. The
   recommender and quizzes don't need examples.

**What it changes:**
- ADR-010's reading practice works on OpenJLPT's examples: about 8,000
  usable sentences, smaller than Tatoeba's 102,568 but enough for N5–N2.
- The supplement in rule 3 is a new, small slice-1 file.

---

## Without OpenJLPT: Waller's lists and Tatoeba's index against JMdict

**Pass: counted, reported and ruled.** 98.0% of JLPT rows match one JMdict
entry by spelling and reading alone, and three fixed rules settle all but
24 of the rest (15 unmatched). Of Tatoeba's Japanese sentences, 59.6% are
indexed, and 95.2% of their index tokens map to one entry. With a 10-word
override list, 97.1% of indexed sentences map completely.

```
./run.sh dict > results.txt      # needs spike 1's database (container juku-dict)
```

`mapping.sql` holds the rules; `report.sql` the counts; `jlpt_tsv.py` turns
the CSVs into a COPY file. [results.txt](4-jlpt-mapping/results/results.txt) is the full output.
The mapping runs in about 5 s.

### Data

- **JLPT lists:** Jonathan Waller's N5–N1 lists (tanos.co.uk, CC BY), as
  republished by stephenmk/yomitan-jlpt-vocab at commit `b062d4e` (CC BY-SA
  4.0). That repo adds a **hand-chosen JMdict ID to each row** and replaces
  a few rare spellings with common ones. The spike maps the words *without*
  those IDs, then uses them as a reference. tanos.co.uk itself didn't
  respond on 2026-10-28.
- The official JLPT has published no word lists since 2010, so these levels
  are community estimates (Phase 2, D2 already says so).
- JMdict_e 2026-10-28 and Tatoeba 2026-10-24, as loaded by spike 1.

### The rules

A JLPT kanji word matches entries with that spelling *and* a reading valid
for it (`re_restr`, `re_nokanji`). A kana word matches entries with that
reading. A Tatoeba token uses its `(#id)` when it has one, then its
spelling, then its reading. When several entries match, these rules run in
order, and the first that leaves one entry decides:

1. **R1, priority:** keep entries whose matched form has a JMdict priority
   tag (news1, ichi1, spec1, gai1, nfXX).
2. **R2, primary form:** keep entries where the matched form is the
   entry's first.
3. **R3, kana word:** for a word written in kana, keep entries with no
   kanji spelling, or marked "usually kana" (uk) in their first sense.

**Anything still tied is ambiguous: reported and left out, never guessed.**

Proposed for slice 1, measured here but not yet in `mapping.sql`:

4. **R4, Waller's gloss (JLPT only):** keep candidates whose first-sense
   glosses share a word with Waller's English definition. It settles 9 of
   the 24 ambiguous rows (8 agree with the reference).
5. **A hand-written override list for Tatoeba's top function words:**
   の, ん, そう, なんて, 何, くらい and four more cover **99.5%** of
   ambiguous tokens. With them, fully mapped sentences go from 69.1% to
   **97.1% of indexed sentences** (144,045 sentences, 57.9% of all Japanese
   ones).
6. **Single kanji on the N1 list** (乾 かん, 傾 けい…: 14 rows, Waller's
   on-readings) aren't words. They're dropped from the word levels; the
   kanji themselves come from KANJIDIC2.
7. **Words at several levels** (448 entries) take their easiest level.
   Repeated entries inside a level (87 extra rows) collapse to one.

### Numbers

**JLPT rows** (N5–N2 is Juku's range; N1 is included, as Arthur asked):

| Level | Rows | Unique | R1 | R2 | R3 | Ambiguous | Unmatched |
|---|---|---|---|---|---|---|---|
| N5 | 684 | 660 | 18 | 0 | 2 | 4 | 0 |
| N4 | 640 | 626 | 8 | 0 | 4 | 2 | 0 |
| N3 | 1,730 | 1,691 | 27 | 5 | 2 | 5 | 0 |
| N2 | 1,812 | 1,788 | 18 | 2 | 0 | 3 | 1 (田ぼ, a typo for 田んぼ) |
| N1 | 3,427 | 3,361 | 36 | 1 | 5 | 10 | 14 (all single kanji) |
| **All** | **8,293** | **8,126 (98.0%)** | 107 | 8 | 13 | **24** | **15** |

For N5–N2 alone: 4,866 rows, 4,765 unique (97.9%), 14 ambiguous and 1
unmatched.

**Against the hand-added IDs:** 8,230 of the 8,254 rows mapped (99.7%)
agree with the reference (unique 99.9%, R1 91.6%, R2 75%, R3 77%). All 23
disagreements were checked by hand, and **the rules are usually right**:
- 10 "unique" rows are readings that JMdict has since moved to entries of
  their own (管 くだ, 務める, 潮 うしお…), so the reference ID is stale;
- in 9 of the 13 rule-decided kana rows, the reference picks the wrong
  homograph: だんだん as "thank you", コップ as "cop", ボタン as "tree
  peony";
- the reference is right and the rules wrong once (いえ, "no", where R2
  picks 家 "house"), and two are doubtful either way (ド; 元 もと).

**Distinct entries per level** (from the reference, each at its easiest
level): N5 667, N4 630, N3 1,651, N2 1,738, N1 3,061. That's **4,686 for
N5–N2**.

**Tatoeba** (first index line per sentence):

| | Count |
|---|---|
| Japanese sentences | 248,941 |
| Indexed | 148,396 (59.6%) |
| Index tokens | 1,167,242 |
| Mapped uniquely / by `(#id)` / by R1–R3 | 69.7% / 5.3% / 20.3% |
| Ambiguous / unmatched | 4.4% (の alone is 4.2%) / 0.4% |
| Sentences with every token mapped | 102,568 (69.1% of indexed); 97.1% with the override list |

**The hand check (standard checks, a sample of 30):** 30 rule-decided
Tatoeba keys (the 20 most frequent and 10 at random; 28 distinct), each
read against its other candidates. 27 are right, including the particles
は, に, と, か, も and な, whose entries carry all their particle senses.
One is doubtful: 熟, つくづく or つらつら.

### What it would have changed

- **ADR-010's known risk is smaller than feared:** about 2% of JLPT rows
  need a rule, and the ambiguous remainder is 14 rows for N5–N2. Slice 1
  can add R4 and a reviewed override file for the last ones, and report
  the count as planned.
- **Proposed for slice 1:** don't take the hand-added IDs as ground truth.
  They are stale for 10 rows and wrong for at least 9. Map by rule, and
  use the IDs only as a second opinion that flags disagreements for review.
- **LE4 (reading practice) has plenty of material:** about 144,000 fully
  mapped sentences with the override list.
