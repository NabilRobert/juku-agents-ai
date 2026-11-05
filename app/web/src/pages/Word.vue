<script setup lang="ts">
// Kata: one word, what it means, and how it's used: its example sentences, each explainable.
import ExampleSentence from "../components/ExampleSentence.vue";
import JapaneseText from "../components/JapaneseText.vue";
import PostForm from "../components/PostForm.vue";
import type { Example, SentenceBreakdown } from "../lib/types";

defineProps<{
  entry: {
    word_id: string;
    word: string;
    reading: string;
    level: number | null;
    meanings: string[];
    is_known: boolean;
    examples: Example[];
  };
  breakdowns: Record<string, SentenceBreakdown>;
  copy: Record<"meaning" | "examples" | "noExamples" | "iKnowThis" | "youKnowThis", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <section class="card flex flex-wrap items-start justify-between gap-4 sm:p-8">
      <div>
        <p class="text-5xl font-black sm:text-6xl"><JapaneseText :text="entry.word" /></p>
        <p lang="ja" class="mt-2 text-xl text-ink/70">{{ entry.reading }}</p>
      </div>
      <span v-if="entry.level" class="chip text-sm">N{{ entry.level }}</span>
      <div class="w-full">
        <p class="muted text-xs font-semibold uppercase">{{ copy.meaning }}</p>
        <p class="text-lg font-medium">{{ entry.meanings.join("; ") }}</p>
      </div>
      <p v-if="entry.is_known" class="chip bg-lemon text-ink">✓ {{ copy.youKnowThis }}</p>
      <PostForm v-else :action="`/kata/${entry.word_id}/dikuasai`">
        <input type="hidden" name="back_to" value="word" />
        <button type="submit" class="btn">✓ {{ copy.iKnowThis }}</button>
      </PostForm>
    </section>

    <h2 class="section-title mt-8 mb-3">{{ copy.examples }}</h2>
    <ul class="space-y-3">
      <li v-for="example in entry.examples" :key="example.ja" class="card border-l-4 border-l-amber">
        <ExampleSentence :example="example" :breakdown="breakdowns[example.ja]" />
      </li>
    </ul>
    <p v-if="entry.examples.length === 0" class="alert">{{ copy.noExamples }}</p>
  </div>
</template>
