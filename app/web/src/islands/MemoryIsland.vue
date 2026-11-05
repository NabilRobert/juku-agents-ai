<script setup lang="ts">
// "Shiori ingat…" (MEM-R5): every note with its evidence and age, and the words
// the learner knows. Each can be corrected here: remove a note, mark it wrong,
// or unmark a word. The server renders the data; this island only sends the
// corrections and drops what was corrected.
import { ref } from "vue";
import { postJson } from "../lib/http";
import type { EvidenceEvent, KnownWord, MemoryCopy, MemoryNote } from "./memory-types";

const props = defineProps<{
  notes: MemoryNote[];
  words: KnownWord[];
  copy: MemoryCopy;
  csrf: string;
}>();

const notes = ref([...props.notes]);
const words = ref([...props.words]);
const message = ref("");

/** One evidence row as a line: its date, what happened, the word, and whether the answer was right. */
function describe(item: EvidenceEvent): string {
  const parts = [item.occurred_on, props.copy.events[item.event_type] ?? item.event_type];
  if (item.word) parts.push(`${item.word} (${item.reading})`);
  if (item.is_correct !== null) parts.push(item.is_correct ? props.copy.right : props.copy.wrong);
  return parts.join(" · ");
}

async function send(url: string, done: string, drop: () => void): Promise<void> {
  const response = await postJson(url, {}, props.csrf);
  if (response.ok) {
    drop();
    message.value = done;
  } else {
    message.value = props.copy.failed;
  }
}

function removeNote(note: MemoryNote): Promise<void> {
  return send(`/ingat/catatan/${note.note_id}/hapus`, props.copy.removed, () => {
    notes.value = notes.value.filter((item) => item.note_id !== note.note_id);
  });
}

function markWrong(note: MemoryNote): Promise<void> {
  return send(`/ingat/catatan/${note.note_id}/salah`, props.copy.markedWrong, () => {
    notes.value = notes.value.filter((item) => item.note_id !== note.note_id);
  });
}

function unmark(word: KnownWord): Promise<void> {
  return send(`/ingat/kata/${word.word_id}/belum`, props.copy.unmarked, () => {
    words.value = words.value.filter((item) => item.word_id !== word.word_id);
  });
}
</script>

<template>
  <div class="space-y-6">
    <p v-if="message" role="status" class="alert">{{ message }}</p>
    <section>
      <h2 class="section-title">{{ copy.notesHeading }}</h2>
      <p v-if="notes.length === 0" class="muted mt-2">{{ copy.noNotes }}</p>
      <article v-for="note in notes" :key="note.note_id" class="note card mt-3 border-l-4 border-l-orange">
        <p class="font-semibold">{{ note.text }}</p>
        <p class="muted mt-1 text-xs">
          <span class="chip mr-1">{{ copy.categories[note.category] ?? note.category }}</span>
          {{ copy.notedOn }} {{ note.noted_on }} · {{ note.age_days }} {{ copy.daysAgo }}
        </p>
        <ul class="evidence mt-3 space-y-1 rounded-xl bg-cream p-3 text-xs">
          <li v-for="item in note.evidence" :key="item.event_id">{{ describe(item) }}</li>
        </ul>
        <div class="mt-3 flex flex-wrap gap-2">
          <button type="button" class="remove btn-quiet" @click="removeNote(note)">{{ copy.remove }}</button>
          <button type="button" class="mark-wrong btn-quiet" @click="markWrong(note)">{{ copy.markWrong }}</button>
        </div>
      </article>
    </section>
    <section>
      <h2 class="section-title">{{ copy.wordsHeading }}</h2>
      <p v-if="words.length === 0" class="muted mt-2">{{ copy.noWords }}</p>
      <ul class="mt-3 grid gap-2 sm:grid-cols-2">
        <li v-for="word in words" :key="word.word_id" class="known-word card flex items-center justify-between gap-2 p-3">
          <span><span lang="ja" class="text-lg font-bold">{{ word.word }}</span> <span lang="ja" class="muted">{{ word.reading }}</span></span>
          <button type="button" class="unmark btn-quiet py-1 text-xs" @click="unmark(word)">{{ copy.unmark }}</button>
        </li>
      </ul>
    </section>
  </div>
</template>
