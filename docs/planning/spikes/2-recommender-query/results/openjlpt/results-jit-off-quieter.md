Quieter run. Start: load averages: 4.73 6.78 7.97. End: load averages: 5.37 6.81 7.96.

OpenJLPT tables, jit off; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 4.6 / 6.6 / 22.9 | 4.4 / 6.3 / 21.1 | 10 |
| N5 | 0 | `find_reading_sentences` | 1.7 / 2.4 / 2.8 | 1.5 / 2.1 / 2.6 | 10 |
| N5 | 100 | `recommend_words` | 5.1 / 7.3 / 9.6 | 4.8 / 6.4 / 9.2 | 10 |
| N5 | 100 | `find_reading_sentences` | 4.1 / 5.9 / 6.5 | 3.8 / 5.4 / 5.9 | 10 |
| N5 | 500 | `recommend_words` | 7.5 / 10.4 / 19.4 | 6.9 / 9.9 / 18.8 | 10 |
| N5 | 500 | `find_reading_sentences` | 10.3 / 12.2 / 13.3 | 9.1 / 11.1 / 12.3 | 10 |
| N4 | 0 | `recommend_words` | 6.9 / 14.8 / 48.8 | 6.3 / 14.1 / 47.8 | 10 |
| N4 | 100 | `recommend_words` | 6.7 / 8.0 / 8.5 | 6.4 / 7.1 / 7.7 | 10 |
| N4 | 500 | `recommend_words` | 9.1 / 10.3 / 15.9 | 8.3 / 9.6 / 13.1 | 10 |
| N3 | 0 | `recommend_words` | 12.4 / 14.2 / 22.5 | 11.2 / 13.4 / 21.4 | 10 |
| N3 | 100 | `recommend_words` | 12.7 / 14.3 / 19.4 | 11.6 / 13.5 / 19.0 | 10 |
| N3 | 500 | `recommend_words` | 14.3 / 20.9 / 22.2 | 13.3 / 19.2 / 21.1 | 10 |
| N2 | 0 | `recommend_words` | 16.7 / 19.0 / 29.9 | 15.7 / 18.3 / 28.9 | 10 |
| N2 | 100 | `recommend_words` | 23.5 / 79.2 / 99.2 | 22.7 / 78.5 / 97.8 | 10 |
| N2 | 500 | `recommend_words` | 53.9 / 94.7 / 102.4 | 53.1 / 93.1 / 101.9 | 10 |

Worst single round trip: **102.4 ms** (limit 200 ms).

<details><summary>First four results of each run</summary>

```json
{
 "recommend_words N5 known=0": [
  {
   "id": "537f8af3d6",
   "word": "一つ",
   "reading": "ひとつ",
   "level": 5,
   "new_k": "一",
   "leverage": 9,
   "reason": "1 kanji baru: 一, muncul di 9 kata N5."
  },
  {
   "id": "9d8f862791",
   "word": "一",
   "reading": "いち",
   "level": 5,
   "new_k": "一",
   "leverage": 9,
   "reason": "1 kanji baru: 一, muncul di 9 kata N5."
  },
  {
   "id": "3a2de0afca",
   "word": "大きな",
   "reading": "おおきな",
   "level": 5,
   "new_k": "大",
   "leverage": 9,
   "reason": "1 kanji baru: 大, muncul di 9 kata N5."
  },
  {
   "id": "8fa5a63fc7",
   "word": "大きい",
   "reading": "おおきい",
   "level": 5,
   "new_k": "大",
   "leverage": 9,
   "reason": "1 kanji baru: 大, muncul di 9 kata N5."
  }
 ],
 "find_reading_sentences N5 known=0": [
  {
   "sentence_id": 2191,
   "ja": "こんばんは。",
   "new_word": "6c0551dd8a"
  },
  {
   "sentence_id": 4339,
   "ja": "ファイトだ。",
   "new_word": "a6b276960f"
  },
  {
   "sentence_id": 4348,
   "ja": "ふざけるな！",
   "new_word": "76502785af"
  },
  {
   "sentence_id": 5356,
   "ja": "以上ですか？",
   "new_word": "13ab63d79a"
  }
 ],
 "recommend_words N5 known=100": [
  {
   "id": "537f8af3d6",
   "word": "一つ",
   "reading": "ひとつ",
   "level": 5,
   "new_k": "一",
   "leverage": 9,
   "reason": "1 kanji baru: 一, muncul di 9 kata N5."
  },
  {
   "id": "9d8f862791",
   "word": "一",
   "reading": "いち",
   "level": 5,
   "new_k": "一",
   "leverage": 9,
   "reason": "1 kanji baru: 一, muncul di 9 kata N5."
  },
  {
   "id": "3a2de0afca",
   "word": "大きな",
   "reading": "おおきな",
   "level": 5,
   "new_k": "大",
   "leverage": 9,
   "reason": "1 kanji baru: 大, muncul di 9 kata N5."
  },
  {
   "id": "8fa5a63fc7",
   "word": "大きい",
   "reading": "おおきい",
   "level": 5,
   "new_k": "大",
   "leverage": 9,
   "reason": "1 kanji baru: 大, muncul di 9 kata N5."
  }
 ],
 "find_reading_sentences N5 known=100": [
  {
   "sentence_id": 4339,
   "ja": "ファイトだ。",
   "new_word": "a6b276960f"
  },
  {
   "sentence_id": 4348,
   "ja": "ふざけるな！",
   "new_word": "76502785af"
  },
  {
   "sentence_id": 5356,
   "ja": "以上ですか？",
   "new_word": "13ab63d79a"
  },
  {
   "sentence_id": 5752,
   "ja": "初耳ですね。",
   "new_word": "45f5de7d2d"
  }
 ],
 "recommend_words N5 known=500": [
  {
   "id": "04e80a2ba1",
   "word": "月曜日",
   "reading": "げつようび",
   "level": 5,
   "new_k": "曜",
   "leverage": 7,
   "reason": "1 kanji baru: 曜, muncul di 7 kata N5."
  },
  {
   "id": "44d9d70862",
   "word": "水曜日",
   "reading": "すいようび",
   "level": 5,
   "new_k": "曜",
   "leverage": 7,
   "reason": "1 kanji baru: 曜, muncul di 7 kata N5."
  },
  {
   "id": "b00c4af0a2",
   "word": "金曜日",
   "reading": "きんようび",
   "level": 5,
   "new_k": "曜",
   "leverage": 7,
   "reason": "1 kanji baru: 曜, muncul di 7 kata N5."
  },
  {
   "id": "efac1fc502",
   "word": "肉",
   "reading": "にく",
   "level": 5,
   "new_k": "肉",
   "leverage": 4,
   "reason": "1 kanji baru: 肉, muncul di 4 kata N5."
  }
 ],
 "find_reading_sentences N5 known=500": [
  {
   "sentence_id": 5416,
   "ja": "住めば都。",
   "new_word": "53162e310d"
  },
  {
   "sentence_id": 12360,
   "ja": "閉会した。",
   "new_word": "3beb5d12ff"
  },
  {
   "sentence_id": 2775,
   "ja": "その内訳は？",
   "new_word": "d1a7b5a2a1"
  },
  {
   "sentence_id": 4339,
   "ja": "ファイトだ。",
   "new_word": "a6b276960f"
  }
 ],
 "recommend_words N4 known=0": [
  {
   "id": "782272bfda",
   "word": "物",
   "reading": "もの",
   "level": 5,
   "new_k": "物",
   "leverage": 15,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 物, muncul di 15 kata N4."
  },
  {
   "id": "5c89b3094a",
   "word": "食べ物",
   "reading": "たべもの",
   "level": 5,
   "new_k": "物",
   "leverage": 15,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 物, muncul di 15 kata N4."
  },
  {
   "id": "ada066edfd",
   "word": "会う",
   "reading": "あう",
   "level": 5,
   "new_k": "会",
   "leverage": 10,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 会, muncul di 10 kata N4."
  },
  {
   "id": "1763fc412a",
   "word": "上手",
   "reading": "じょうず",
   "level": 5,
   "new_k": "手",
   "leverage": 9,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 手, muncul di 9 kata N4."
  }
 ],
 "recommend_words N4 known=100": [
  {
   "id": "782272bfda",
   "word": "物",
   "reading": "もの",
   "level": 5,
   "new_k": "物",
   "leverage": 15,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 物, muncul di 15 kata N4."
  },
  {
   "id": "5c89b3094a",
   "word": "食べ物",
   "reading": "たべもの",
   "level": 5,
   "new_k": "物",
   "leverage": 15,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 物, muncul di 15 kata N4."
  },
  {
   "id": "ada066edfd",
   "word": "会う",
   "reading": "あう",
   "level": 5,
   "new_k": "会",
   "leverage": 10,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 会, muncul di 10 kata N4."
  },
  {
   "id": "1763fc412a",
   "word": "上手",
   "reading": "じょうず",
   "level": 5,
   "new_k": "手",
   "leverage": 9,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 手, muncul di 9 kata N4."
  }
 ],
 "recommend_words N4 known=500": [
  {
   "id": "04e80a2ba1",
   "word": "月曜日",
   "reading": "げつようび",
   "level": 5,
   "new_k": "曜",
   "leverage": 7,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 曜, muncul di 7 kata N4."
  },
  {
   "id": "0dbf9ef8ca",
   "word": "火曜日",
   "reading": "かようび",
   "level": 5,
   "new_k": "曜",
   "leverage": 7,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 曜, muncul di 7 kata N4."
  },
  {
   "id": "44d9d70862",
   "word": "水曜日",
   "reading": "すいようび",
   "level": 5,
   "new_k": "曜",
   "leverage": 7,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 曜, muncul di 7 kata N4."
  },
  {
   "id": "a95b0a87ad",
   "word": "習う",
   "reading": "ならう",
   "level": 5,
   "new_k": "習",
   "leverage": 5,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 習, muncul di 5 kata N4."
  }
 ],
 "recommend_words N3 known=0": [
  {
   "id": "54e1f7a772",
   "word": "合う",
   "reading": "あう",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "675232ef05",
   "word": "間に合う",
   "reading": "まにあう",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "2d86d7e0fc",
   "word": "場合",
   "reading": "ばあい",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "7a84208708",
   "word": "要る",
   "reading": "いる",
   "level": 5,
   "new_k": "要",
   "leverage": 9,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 要, muncul di 9 kata N3."
  }
 ],
 "recommend_words N3 known=100": [
  {
   "id": "54e1f7a772",
   "word": "合う",
   "reading": "あう",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "675232ef05",
   "word": "間に合う",
   "reading": "まにあう",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "2d86d7e0fc",
   "word": "場合",
   "reading": "ばあい",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "7a84208708",
   "word": "要る",
   "reading": "いる",
   "level": 5,
   "new_k": "要",
   "leverage": 9,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 要, muncul di 9 kata N3."
  }
 ],
 "recommend_words N3 known=500": [
  {
   "id": "54e1f7a772",
   "word": "合う",
   "reading": "あう",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "675232ef05",
   "word": "間に合う",
   "reading": "まにあう",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "2d86d7e0fc",
   "word": "場合",
   "reading": "ばあい",
   "level": 4,
   "new_k": "合",
   "leverage": 16,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 合, muncul di 16 kata N3."
  },
  {
   "id": "356e03170b",
   "word": "付く",
   "reading": "つく",
   "level": 4,
   "new_k": "付",
   "leverage": 9,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 付, muncul di 9 kata N3."
  }
 ],
 "recommend_words N2 known=0": [
  {
   "id": "4aa59e0065",
   "word": "地平線",
   "reading": "ちへいせん",
   "level": 3,
   "new_k": "線",
   "leverage": 11,
   "reason": "Kata N3 yang belum dikuasai. 1 kanji baru: 線, muncul di 11 kata N2."
  },
  {
   "id": "da94019cdd",
   "word": "線",
   "reading": "せん",
   "level": 4,
   "new_k": "線",
   "leverage": 11,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 線, muncul di 11 kata N2."
  },
  {
   "id": "4092bfd9bb",
   "word": "角",
   "reading": "かど",
   "level": 5,
   "new_k": "角",
   "leverage": 11,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 角, muncul di 11 kata N2."
  },
  {
   "id": "778765a79e",
   "word": "角",
   "reading": "つの",
   "level": 3,
   "new_k": "角",
   "leverage": 11,
   "reason": "Kata N3 yang belum dikuasai. 1 kanji baru: 角, muncul di 11 kata N2."
  }
 ],
 "recommend_words N2 known=100": [
  {
   "id": "4aa59e0065",
   "word": "地平線",
   "reading": "ちへいせん",
   "level": 3,
   "new_k": "線",
   "leverage": 11,
   "reason": "Kata N3 yang belum dikuasai. 1 kanji baru: 線, muncul di 11 kata N2."
  },
  {
   "id": "da94019cdd",
   "word": "線",
   "reading": "せん",
   "level": 4,
   "new_k": "線",
   "leverage": 11,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 線, muncul di 11 kata N2."
  },
  {
   "id": "4092bfd9bb",
   "word": "角",
   "reading": "かど",
   "level": 5,
   "new_k": "角",
   "leverage": 11,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 角, muncul di 11 kata N2."
  },
  {
   "id": "778765a79e",
   "word": "角",
   "reading": "つの",
   "level": 3,
   "new_k": "角",
   "leverage": 11,
   "reason": "Kata N3 yang belum dikuasai. 1 kanji baru: 角, muncul di 11 kata N2."
  }
 ],
 "recommend_words N2 known=500": [
  {
   "id": "4aa59e0065",
   "word": "地平線",
   "reading": "ちへいせん",
   "level": 3,
   "new_k": "線",
   "leverage": 11,
   "reason": "Kata N3 yang belum dikuasai. 1 kanji baru: 線, muncul di 11 kata N2."
  },
  {
   "id": "da94019cdd",
   "word": "線",
   "reading": "せん",
   "level": 4,
   "new_k": "線",
   "leverage": 11,
   "reason": "Kata N4 yang belum dikuasai. 1 kanji baru: 線, muncul di 11 kata N2."
  },
  {
   "id": "4092bfd9bb",
   "word": "角",
   "reading": "かど",
   "level": 5,
   "new_k": "角",
   "leverage": 11,
   "reason": "Kata N5 yang belum dikuasai. 1 kanji baru: 角, muncul di 11 kata N2."
  },
  {
   "id": "778765a79e",
   "word": "角",
   "reading": "つの",
   "level": 3,
   "new_k": "角",
   "leverage": 11,
   "reason": "Kata N3 yang belum dikuasai. 1 kanji baru: 角, muncul di 11 kata N2."
  }
 ]
}
```
</details>
