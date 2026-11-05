// What the server renders into every page (app/src/juku_app/templates/base.html and each page's template).
export interface Shell {
  csrf: string;
  signedIn: boolean;
  current: string;
  sections: { slug: string; label: string }[];
  aboutData: string;
}

export interface PageData {
  component: string;
  props: Record<string, unknown>;
}

// The shapes below follow the server's models (juku_data.engine.models), as JSON.
export interface Word {
  word_id: string;
  word: string;
  reading: string;
  level: number;
  meanings: string[];
  reason: string;
}

export interface LevelProgress {
  level_name: string;
  words_known: number;
  words_total: number;
  kanji_known: number;
  kanji_total: number;
}

export interface Progress {
  known_words: number;
  levels: LevelProgress[];
}

export interface QuizItem {
  word_id: string;
  kind: "meaning" | "reading";
  prompt: string;
  options: string[];
}

export interface QuizCopy {
  correct: string;
  wrong: string;
  next: string;
  done: string;
}

export interface ChatCopy {
  placeholder: string;
  send: string;
  unverified: string;
  helpful: string;
  unhelpful: string;
  failed: string;
}
