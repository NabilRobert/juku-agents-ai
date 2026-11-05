// OpenJLPT writes furigana as {漢字|かんじ} inside the sentence. The server checks it spells the sentence
// (juku_data.dictionary.furigana); the page splits it into plain runs and runs with a reading.
export interface Run {
  text: string;
  reading: string | null;
}

const MARKUP = /\{([^|}]+)\|([^}]+)\}/g;
const KANJI = /[々一-鿿]/;

export function furiganaRuns(ja: string, furigana: string | null): Run[] {
  if (!furigana) return [{ text: ja, reading: null }];
  const runs: Run[] = [];
  let position = 0;
  for (const match of furigana.matchAll(MARKUP)) {
    const [whole, text = "", reading = ""] = match;
    if (match.index > position) runs.push({ text: furigana.slice(position, match.index), reading: null });
    runs.push({ text, reading });
    position = match.index + whole.length;
  }
  if (position < furigana.length) runs.push({ text: furigana.slice(position), reading: null });
  return runs;
}

export function isKanji(character: string): boolean {
  return KANJI.test(character);
}
