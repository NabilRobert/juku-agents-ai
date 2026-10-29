Query v1, jit off.

<!-- learner_word rows: 2,125,332 -->
| Level | Known words | Tool | Round trip ms (p50 / p95 / max) | SQL ms (p50 / p95 / max) | Results |
|---|---|---|---|---|---|
| N5 | 0 | `recommend_words` | 5.2 / 7.1 / 76.4 | 4.9 / 6.7 / 75.7 | 10 |
| N5 | 0 | `find_reading_sentences` | 3.8 / 6.2 / 14.0 | 3.1 / 5.4 / 13.5 | 10 |
| N5 | 100 | `recommend_words` | 6.2 / 7.3 / 9.0 | 5.7 / 6.8 / 8.1 | 10 |
| N5 | 100 | `find_reading_sentences` | 33.5 / 43.5 / 98.4 | 32.4 / 42.9 / 97.4 | 10 |
| N5 | 500 | `recommend_words` | 5.0 / 6.1 / 7.7 | 4.8 / 5.8 / 7.4 | 10 |
| N5 | 500 | `find_reading_sentences` | 77.3 / 136.9 / 185.1 | 76.9 / 136.4 / 184.4 | 10 |
| N4 | 0 | `recommend_words` | 9.1 / 15.1 / 27.7 | 8.6 / 14.7 / 27.3 | 10 |
| N4 | 100 | `recommend_words` | 7.8 / 10.8 / 12.6 | 7.6 / 10.2 / 12.2 | 10 |
| N4 | 500 | `recommend_words` | 8.8 / 10.9 / 12.7 | 8.5 / 10.5 / 12.5 | 10 |
| N3 | 0 | `recommend_words` | 15.1 / 27.6 / 43.0 | 14.3 / 24.4 / 40.4 | 10 |
| N3 | 100 | `recommend_words` | 16.0 / 19.0 / 24.6 | 15.1 / 18.3 / 22.4 | 10 |
| N3 | 500 | `recommend_words` | 18.0 / 27.6 / 291.7 | 17.4 / 26.3 / 291.0 | 10 |
| N2 | 0 | `recommend_words` | 20.7 / 22.7 / 36.6 | 19.9 / 21.5 / 35.9 | 10 |
| N2 | 100 | `recommend_words` | 22.2 / 35.4 / 69.0 | 21.1 / 33.5 / 66.6 | 10 |
| N2 | 500 | `recommend_words` | 26.4 / 31.7 / 75.9 | 25.9 / 31.2 / 75.5 | 10 |

Worst single round trip: **291.7 ms** (limit 200 ms).

<details><summary>First five results of each run</summary>

```json
{
 "recommend_words N5 known=0": [
  {
   "ent_seq": 1243850,
   "written": "９日",
   "reading": "ここのか",
   "level": 5,
   "new_k": "日",
   "leverage": 26,
   "reason": "1 kanji baru: 日, muncul di 26 kata umum N5."
  },
  {
   "ent_seq": 1268570,
   "written": "５日",
   "reading": "いつか",
   "level": 5,
   "new_k": "日",
   "leverage": 26,
   "reason": "1 kanji baru: 日, muncul di 26 kata umum N5."
  },
  {
   "ent_seq": 1301330,
   "written": "３日",
   "reading": "みっか",
   "level": 5,
   "new_k": "日",
   "leverage": 26,
   "reason": "1 kanji baru: 日, muncul di 26 kata umum N5."
  },
  {
   "ent_seq": 1577100,
   "written": "何",
   "reading": "なに",
   "level": 5,
   "new_k": "何",
   "leverage": 13,
   "reason": "1 kanji baru: 何, muncul di 13 kata umum N5."
  },
  {
   "ent_seq": 1920240,
   "written": "何の",
   "reading": "どの",
   "level": 5,
   "new_k": "何",
   "leverage": 13,
   "reason": "1 kanji baru: 何, muncul di 13 kata umum N5."
  }
 ],
 "find_reading_sentences N5 known=0": [
  {
   "sentence_id": 75114,
   "text": "死ね！",
   "new_word": 1310730,
   "indonesian": "Mati sana!"
  },
  {
   "sentence_id": 81008,
   "text": "眠い！",
   "new_word": 1529330,
   "indonesian": "Aku ngantuk!"
  },
  {
   "sentence_id": 81591,
   "text": "本気？",
   "new_word": 1522370,
   "indonesian": "Serius?"
  },
  {
   "sentence_id": 152226,
   "text": "私も。",
   "new_word": 1311110,
   "indonesian": "Aku juga."
  },
  {
   "sentence_id": 175045,
   "text": "元気？",
   "new_word": 1260720,
   "indonesian": "Apa kabar?"
  }
 ],
 "recommend_words N5 known=100": [
  {
   "ent_seq": 1577100,
   "written": "何",
   "reading": "なに",
   "level": 5,
   "new_k": "何",
   "leverage": 13,
   "reason": "1 kanji baru: 何, muncul di 13 kata umum N5."
  },
  {
   "ent_seq": 1920240,
   "written": "何の",
   "reading": "どの",
   "level": 5,
   "new_k": "何",
   "leverage": 13,
   "reason": "1 kanji baru: 何, muncul di 13 kata umum N5."
  },
  {
   "ent_seq": 1188760,
   "written": "何時",
   "reading": "いつ",
   "level": 5,
   "new_k": "何",
   "leverage": 13,
   "reason": "1 kanji baru: 何, muncul di 13 kata umum N5."
  },
  {
   "ent_seq": 1516930,
   "written": "方",
   "reading": "ほう",
   "level": 5,
   "new_k": "方",
   "leverage": 9,
   "reason": "1 kanji baru: 方, muncul di 9 kata umum N5."
  },
  {
   "ent_seq": 1516925,
   "written": "方",
   "reading": "かた",
   "level": 5,
   "new_k": "方",
   "leverage": 9,
   "reason": "1 kanji baru: 方, muncul di 9 kata umum N5."
  }
 ],
 "find_reading_sentences N5 known=100": [
  {
   "sentence_id": 75114,
   "text": "死ね！",
   "new_word": 1310730,
   "indonesian": "Mati sana!"
  },
  {
   "sentence_id": 81008,
   "text": "眠い！",
   "new_word": 1529330,
   "indonesian": "Aku ngantuk!"
  },
  {
   "sentence_id": 81591,
   "text": "本気？",
   "new_word": 1522370,
   "indonesian": "Serius?"
  },
  {
   "sentence_id": 175045,
   "text": "元気？",
   "new_word": 1260720,
   "indonesian": "Apa kabar?"
  },
  {
   "sentence_id": 175405,
   "text": "嫌だ！",
   "new_word": 1587610,
   "indonesian": "Tidak!"
  }
 ],
 "recommend_words N5 known=500": [
  {
   "ent_seq": 1163940,
   "written": "一寸",
   "reading": "ちょっと",
   "level": 5,
   "new_k": "寸",
   "leverage": 2,
   "reason": "1 kanji baru: 寸, muncul di 2 kata umum N5."
  },
  {
   "ent_seq": 1169250,
   "written": "引く",
   "reading": "ひく",
   "level": 5,
   "new_k": "引",
   "leverage": 2,
   "reason": "1 kanji baru: 引, muncul di 2 kata umum N5."
  },
  {
   "ent_seq": 1202450,
   "written": "開ける",
   "reading": "あける",
   "level": 5,
   "new_k": "開",
   "leverage": 2,
   "reason": "1 kanji baru: 開, muncul di 2 kata umum N5."
  },
  {
   "ent_seq": 1315140,
   "written": "字引",
   "reading": "じびき",
   "level": 5,
   "new_k": "引",
   "leverage": 2,
   "reason": "1 kanji baru: 引, muncul di 2 kata umum N5."
  },
  {
   "ent_seq": 1430620,
   "written": "直ぐに",
   "reading": "すぐに",
   "level": 5,
   "new_k": "直",
   "leverage": 2,
   "reason": "1 kanji baru: 直, muncul di 2 kata umum N5."
  }
 ],
 "find_reading_sentences N5 known=500": [
  {
   "sentence_id": 81008,
   "text": "眠い！",
   "new_word": 1529330,
   "indonesian": "Aku ngantuk!"
  },
  {
   "sentence_id": 81591,
   "text": "本気？",
   "new_word": 1522370,
   "indonesian": "Serius?"
  },
  {
   "sentence_id": 184053,
   "text": "乾杯！",
   "new_word": 1590950,
   "indonesian": "Bersulang!"
  },
  {
   "sentence_id": 4739,
   "text": "行くよ。",
   "new_word": 1578850,
   "indonesian": "Ayo pergi"
  },
  {
   "sentence_id": 77455,
   "text": "恋かな？",
   "new_word": 1558670,
   "indonesian": "Apakah ini cinta?"
  }
 ],
 "recommend_words N4 known=0": [
  {
   "ent_seq": 1156800,
   "written": "意味",
   "reading": "いみ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1160820,
   "written": "一つ",
   "reading": "ひとつ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1165970,
   "written": "一番",
   "reading": "いちばん",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1171010,
   "written": "右",
   "reading": "みぎ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1173720,
   "written": "映画",
   "reading": "えいが",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N4 known=100": [
  {
   "ent_seq": 1536350,
   "written": "夜",
   "reading": "よる",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1553170,
   "written": "旅行",
   "reading": "りょこう",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1554310,
   "written": "料理",
   "reading": "りょうり",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1559160,
   "written": "練習",
   "reading": "れんしゅう",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1576060,
   "written": "一昨年",
   "reading": "おととし",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N4 known=500": [
  {
   "ent_seq": 1067470,
   "written": "スカート",
   "reading": "スカート",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1070790,
   "written": "ストーブ",
   "reading": "ストーブ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1072590,
   "written": "スプーン",
   "reading": "スプーン",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1073210,
   "written": "スポーツ",
   "reading": "スポーツ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1073900,
   "written": "スリッパ",
   "reading": "スリッパ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N3 known=0": [
  {
   "ent_seq": 1153930,
   "written": "安全",
   "reading": "あんぜん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156530,
   "written": "意見",
   "reading": "いけん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156800,
   "written": "意味",
   "reading": "いみ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1160820,
   "written": "一つ",
   "reading": "ひとつ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1165970,
   "written": "一番",
   "reading": "いちばん",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N3 known=100": [
  {
   "ent_seq": 1153930,
   "written": "安全",
   "reading": "あんぜん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156530,
   "written": "意見",
   "reading": "いけん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1172910,
   "written": "運動",
   "reading": "うんどう",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1198360,
   "written": "会議",
   "reading": "かいぎ",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1215810,
   "written": "関係",
   "reading": "かんけい",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N3 known=500": [
  {
   "ent_seq": 1153930,
   "written": "安全",
   "reading": "あんぜん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156530,
   "written": "意見",
   "reading": "いけん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1172910,
   "written": "運動",
   "reading": "うんどう",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1198360,
   "written": "会議",
   "reading": "かいぎ",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1215810,
   "written": "関係",
   "reading": "かんけい",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N2 known=0": [
  {
   "ent_seq": 1153930,
   "written": "安全",
   "reading": "あんぜん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1155210,
   "written": "以来",
   "reading": "いらい",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156100,
   "written": "委員",
   "reading": "いいん",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156530,
   "written": "意見",
   "reading": "いけん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156800,
   "written": "意味",
   "reading": "いみ",
   "level": 5,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N5 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N2 known=100": [
  {
   "ent_seq": 1153930,
   "written": "安全",
   "reading": "あんぜん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1155210,
   "written": "以来",
   "reading": "いらい",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156100,
   "written": "委員",
   "reading": "いいん",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156530,
   "written": "意見",
   "reading": "いけん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1158450,
   "written": "維持",
   "reading": "いじ",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  }
 ],
 "recommend_words N2 known=500": [
  {
   "ent_seq": 1153930,
   "written": "安全",
   "reading": "あんぜん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1155210,
   "written": "以来",
   "reading": "いらい",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156100,
   "written": "委員",
   "reading": "いいん",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1156530,
   "written": "意見",
   "reading": "いけん",
   "level": 4,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N4 yang belum dikuasai. Tanpa kanji baru."
  },
  {
   "ent_seq": 1158450,
   "written": "維持",
   "reading": "いじ",
   "level": 3,
   "new_k": null,
   "leverage": 0,
   "reason": "Kata N3 yang belum dikuasai. Tanpa kanji baru."
  }
 ]
}
```
</details>
