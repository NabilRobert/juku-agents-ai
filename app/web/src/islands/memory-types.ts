// The memory page's data, as the server renders it (juku_data.memory.models, engine KnownWords).
export interface EvidenceEvent {
  event_id: number;
  event_type: string;
  word: string | null;
  reading: string | null;
  is_correct: boolean | null;
  occurred_on: string;
}

export interface MemoryNote {
  note_id: string;
  category: string;
  text: string;
  evidence: EvidenceEvent[];
  noted_on: string;
  age_days: number;
}

export interface KnownWord {
  word_id: string;
  word: string;
  reading: string;
}

export interface MemoryCopy {
  notesHeading: string;
  noNotes: string;
  wordsHeading: string;
  noWords: string;
  notedOn: string;
  daysAgo: string;
  right: string;
  wrong: string;
  remove: string;
  markWrong: string;
  unmark: string;
  removed: string;
  markedWrong: string;
  unmarked: string;
  failed: string;
  categories: Record<string, string>;
  events: Record<string, string>;
}
