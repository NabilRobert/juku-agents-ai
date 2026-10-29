Run under load: load averages: 16.88 17.90 10.88

OpenJLPT tables, jit off; learner_word_oj rows: 2,125,332.

| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 6.5 / 10.4 / 19.1 | 6.1 / 9.5 / 18.2 | 10 |
| N5 | 0 | `find_reading_sentences` | 2.0 / 2.9 / 4.4 | 1.7 / 2.6 / 4.1 | 10 |
| N5 | 100 | `recommend_words` | 6.3 / 12.7 / 40.7 | 5.9 / 11.8 / 39.5 | 10 |
| N5 | 100 | `find_reading_sentences` | 6.0 / 15.5 / 19.7 | 5.6 / 14.4 / 17.9 | 10 |
| N5 | 500 | `recommend_words` | 9.1 / 27.8 / 53.9 | 8.7 / 25.7 / 37.0 | 10 |
| N5 | 500 | `find_reading_sentences` | 11.8 / 22.6 / 27.3 | 11.2 / 22.0 / 26.7 | 10 |
| N4 | 0 | `recommend_words` | 7.7 / 11.2 / 15.9 | 7.2 / 10.3 / 15.0 | 10 |
| N4 | 100 | `recommend_words` | 8.9 / 16.0 / 80.1 | 8.5 / 15.0 / 77.7 | 10 |
| N4 | 500 | `recommend_words` | 10.7 / 18.0 / 31.0 | 10.3 / 17.2 / 29.8 | 10 |
| N3 | 0 | `recommend_words` | 21.6 / 33.4 / 80.5 | 20.7 / 32.1 / 79.1 | 10 |
| N3 | 100 | `recommend_words` | 14.6 / 27.6 / 50.0 | 14.1 / 26.5 / 48.3 | 10 |
| N3 | 500 | `recommend_words` | 16.7 / 33.3 / 57.7 | 16.2 / 32.3 / 56.3 | 10 |
| N2 | 0 | `recommend_words` | 18.5 / 24.7 / 30.8 | 18.1 / 24.1 / 30.2 | 10 |
| N2 | 100 | `recommend_words` | 19.4 / 33.2 / 57.4 | 19.0 / 32.5 / 56.7 | 10 |
| N2 | 500 | `recommend_words` | 82.2 / 192.8 / 274.0 | 80.8 / 192.1 / 271.6 | 10 |

Worst single round trip: **274.0 ms** (limit 200 ms).

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
