// What the server renders into every page (app/src/juku_app/templates/base.html and each page's template).
export interface Shell {
  csrf: string;
  signedIn: boolean;
  current: string;
  sections: { slug: string; label: string }[];
  aboutData: string;
  language: "id" | "en";
  languageLabel: string;
  ownerLinks: { href: string; label: string }[];
  study: StudyCopy;
}

/** The words the shared study components (kanji popup, sentence explanation) show on every page. */
export interface StudyCopy {
  explain: string;
  hide: string;
  words: string;
  grammar: string;
  grammarNote: string;
  known: string;
  kanjiWords: string;
  strokes: string;
  loading: string;
  notKanji: string;
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

// Studying words in context (juku_data.engine.models: Example ... KanjiEntry).
export interface Example {
  ja: string;
  furigana: string | null;
  en: string | null;
}

export interface GrammarSummary {
  grammar_id: string;
  pattern: string;
  level: number;
  meaning: string;
}

export interface TokenWord {
  word_id: string;
  word: string;
  reading: string;
  level: number | null;
  meanings: string[];
  is_known: boolean;
}

export interface BreakdownToken {
  surface: string;
  reading: string;
  kind: "word" | "grammar" | "name" | "number" | "symbol";
  words: TokenWord[];
}

export interface SentenceBreakdown {
  ja: string;
  tokens: BreakdownToken[];
  grammar: GrammarSummary[];
}

export interface KanjiEntry {
  character: string;
  level: number;
  strokes: number | null;
  onyomi: string[];
  kunyomi: string[];
  meanings: string[];
  words: { word_id: string; word: string; reading: string; level: number; meaning: string; is_known: boolean }[];
}

// The curriculum (juku_data.engine.curriculum_models).
export interface UnitStatus {
  unit_id: number;
  level: number;
  number: number;
  words_total: number;
  words_known: number;
  grammar_total: number;
  grammar_studied: number;
  sentences_total: number;
  sentences_read: number;
  status: "done" | "current" | "later";
}

export interface CurriculumOverview {
  target_level: number;
  units_total: number;
  units_done: number;
  current_unit_id: number | null;
  levels: { level: number; units: UnitStatus[] }[];
}

export interface UnitWord {
  word_id: string;
  word: string;
  reading: string;
  meanings: string[];
  is_known: boolean;
}

export interface UnitGrammar {
  grammar_id: string;
  pattern: string;
  meaning: string;
  is_studied: boolean;
}

export interface UnitSentence {
  sentence_id: number;
  ja: string;
  furigana: string | null;
  en: string | null;
  is_read: boolean;
}

export interface UnitDetail {
  unit: UnitStatus;
  words: UnitWord[];
  kanji: string[];
  grammar: UnitGrammar[];
  sentences: UnitSentence[];
  previous_unit_id: number | null;
  next_unit_id: number | null;
}

export interface TodayPlan {
  unit: UnitStatus | null;
  new_words: UnitWord[];
  words_target: number;
  words_done: number;
  grammar: UnitGrammar | null;
  grammar_done: number;
  sentences: UnitSentence[];
  sentences_target: number;
  sentences_done: number;
  reviews_due: number;
  quiz_target: number;
  quiz_done: number;
  week: WeekDay[];
}

export interface WeekDay {
  day: string;
  done: number;
  target: number;
  is_future: boolean;
}

export interface PlacementResult {
  level: number;
  correct: number;
  total: number;
  placed_through_unit_id: number;
  passed_level: boolean;
}
