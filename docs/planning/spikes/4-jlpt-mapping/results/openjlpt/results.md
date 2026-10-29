# OpenJLPT completeness (spike 4)

OpenJLPT at the pinned commit: 7,811 words (N5 674, N4 630, N3 1,659, N2 1,778, N1 3,070).

## 1. JMdict links

- Linked: 7,800 (99.9%); **unlinked: 11**: 嫋か (N1), 煌々と (N1), 一段と (N2), おまちください (N2), いっていらっしゃい (N2), 何々 (N1), 中腹 (N1), おげんきで (N2), 其れ共 (N1), 矢鱈に (N1), ごぞんじですか (N2)
- Links that don't resolve in JMdict_e 2026-10-28: **0**

## 2. Against this spike's own rule-based mapping (same JLPT lists)

- Same (spelling, reading) in both: 7,561. Same JMdict ID: **7,553 (99.9%)**; different: 8. Not in OpenJLPT under that spelling: 693.
  - いえ (いえ): ours 1191730, OpenJLPT [1583250]
  - どうか (どうか): ours 1632200, OpenJLPT [1454350]
  - せめて (せめて): ours 1006570, OpenJLPT [1675160]
  - ソース (ソース): ours 1075270, OpenJLPT [2843727]
  - ポーズ (ポーズ): ours 1124650, OpenJLPT [2858735]
  - 南 (なん): ours 2869020, OpenJLPT [2833068]
  - 撃つ (うつ): ours 1253570, OpenJLPT [1478010]
  - 何 (なん): ours 2846738, OpenJLPT [1577100]

## 3. Examples

- Words with no example: **566 (7.2%)**; by level: N5 10, N4 6, N3 35, N2 115, N1 400
- Example rows: 13,718; distinct sentences: 12,615

## 4. Example tokens back to word IDs (SudachiPy, split mode C)

Function words (particles, auxiliaries, affixes, symbols) are left out, as in LE4; names and numbers count as known.

| | Tokens | Share of content tokens |
|---|---|---|
| Content tokens | 62,609 | 100% |
| One word ID | 56,784 | 90.7% |
| Several IDs (homographs) | 773 | 1.2% |
| No OpenJLPT word | 5,052 | 8.1% |

Matched by: written 51,840, normalized 3,275, split (mode A) 1,412, kana reading 257.

**Sentences whose every content token maps to one word ID: 7,984 of 12,615 (63.3%)**: the pool for i+1 reading practice.

Counting ない (なく, なかっ, なけれ) as grammar too: **8,339 (66.1%)**.

Most frequent unmatched tokens: ない (400), 父 (80), なく (70), 多く (58), 母 (51), なかっ (43), しれ (34), ドル (34), 顔 (33), 人々 (21), フランス語 (19), 出来 (18), マイル (17), ござい (17), ％ (16), みたい (14), 野球 (14), お前 (14), リンゴ (13), あいつ (13), おじ (13), バラ (12), どういう (12), 夕食 (11), なけれ (11)

Most frequent ambiguous tokens: よう (254), つい (72), おい (29), おき (29), コンピューター (19), わたし (15), なくなっ (15), おり (13), やさしい (11), すみ (10), おく (10), いま (10), ほこり (9), なくし (8), なに (7)

## Hand-check sample: 30 tokens mapped to one word

| Token | How | Word | Reading | First meaning |
|---|---|---|---|---|
| し | written | する | する | to do |
| 教え | written | 教える | おしえる | to teach |
| 入っ | written | 入る | はいる | to enter |
| 彼女 | written | 彼女 | かのじょ | she |
| 山 | written | 山 | やま | mountain |
| 習慣 | written | 習慣 | しゅうかん | custom |
| しまおう | written | しまう | しまう | to finish |
| 器 | written | 器 | うつわ | bowl |
| みんな | written | みんな | みんな | everyone |
| 蛇口 | written | 蛇口 | じゃぐち | faucet |
| 人 | written | 人 | ひと | person |
| 変化 | written | 変化 | へんか | change |
| 日にち | normalized | 日日 | ひにち | every day |
| 火 | written | 火 | ひ | fire |
| 選手 | written | 選手 | せんしゅ | player (in game) |
| 岩石 | written | 岩石 | がんせき | rock |
| 中断 | written | 中断 | ちゅうだん | interruption |
| 感情 | written | 感情 | かんじょう | emotion(s) |
| いる | written | いる | いる | to be |
| 光線 | written | 光線 | こうせん | beam |
| 酸化 | written | 酸化 | さんか | oxidation |
| 満足 | written | 満足 | まんぞく | satisfaction |
| 車輪 | written | 車輪 | しゃりん | (car) wheel |
| 風呂 | written | ふろ | ふろ | bath |
| 起床 | written | 起床 | きしょう | rising |
| ノック | written | ノック | ノック | knock |
| 私 | written | 私 | わたくし | (humble) I |
| 階層 | written | 階層 | かいそう | class |
| ためらわ | written | ためらう | ためらう | to hesitate |
| この | written | この | この | this |
