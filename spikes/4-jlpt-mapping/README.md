# Spike 4: how cleanly do the JLPT lists and Tatoeba's index map to JMdict?

**Pass: counted, reported and ruled.** 98.0% of JLPT rows match one JMdict
entry by spelling and reading alone, and three fixed rules settle all but
24 of the rest (15 unmatched). Of Tatoeba's Japanese sentences, 59.6% are
indexed, and 95.2% of their index tokens map to one entry. With a 10-word
override list, 97.1% of indexed sentences map completely.

```
./run.sh dict > results.txt      # needs spike 1's database (container juku-dict)
```

`mapping.sql` holds the rules; `report.sql` the counts; `jlpt_tsv.py` turns
the CSVs into a COPY file. [results.txt](results.txt) is the full output.
The mapping runs in about 5 s.

## Data

- **JLPT lists:** Jonathan Waller's N5–N1 lists (tanos.co.uk, CC BY), as
  republished by stephenmk/yomitan-jlpt-vocab at commit `b062d4e` (CC BY-SA
  4.0). That repo adds a **hand-chosen JMdict ID to each row** and replaces
  a few rare spellings with common ones. The spike maps the words *without*
  those IDs, then uses them as a reference. tanos.co.uk itself didn't
  respond on 2026-10-28.
- The official JLPT has published no word lists since 2010, so these levels
  are community estimates (Phase 2, D2 already says so).
- JMdict_e 2026-10-28 and Tatoeba 2026-10-24, as loaded by spike 1.

## The rules

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

## Numbers

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

## What it changes in the plan

- **ADR-010's known risk is smaller than feared:** about 2% of JLPT rows
  need a rule, and the ambiguous remainder is 14 rows for N5–N2. Slice 1
  can add R4 and a reviewed override file for the last ones, and report
  the count as planned.
- **Proposed for slice 1:** don't take the hand-added IDs as ground truth.
  They are stale for 10 rows and wrong for at least 9. Map by rule, and
  use the IDs only as a second opinion that flags disagreements for review.
- **LE4 (reading practice) has plenty of material:** about 144,000 fully
  mapped sentences with the override list.
