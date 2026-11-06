<script setup lang="ts">
// One word as a card: the word (its kanji hoverable), its reading and level, its meanings, a link to its
// page, and why it's shown. Used wherever words are listed (recommendations, a curriculum unit, today's
// lesson); the page puts its own action, such as "I know this word", in the `action` slot.
import type { Word } from "../lib/types";
import JapaneseText from "./JapaneseText.vue";

defineProps<{ word: Pick<Word, "word_id" | "word" | "reading" | "meanings"> & Partial<Pick<Word, "level" | "reason">>; examplesLabel: string }>();
</script>

<template>
  <div class="card flex flex-col gap-2">
    <div class="flex items-start justify-between gap-2">
      <div>
        <p class="text-3xl leading-tight font-bold"><JapaneseText :text="word.word" /></p>
        <p lang="ja" class="muted">{{ word.reading }}</p>
      </div>
      <span v-if="word.level" class="chip">N{{ word.level }}</span>
    </div>
    <p class="font-medium">
      {{ word.meanings.slice(0, 2).join("; ") }}
      <a :href="`/kata/${word.word_id}`" class="ml-1 text-sm whitespace-nowrap">{{ examplesLabel }} →</a>
    </p>
    <p v-if="word.reason" class="muted">{{ word.reason }}</p>
    <div v-if="$slots.action" class="mt-auto pt-1"><slot name="action" /></div>
  </div>
</template>
