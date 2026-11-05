<script setup lang="ts">
// Bacaan: sentences with one new word each, each explainable word by word.
import ExampleSentence from "../components/ExampleSentence.vue";
import JapaneseText from "../components/JapaneseText.vue";
import PostForm from "../components/PostForm.vue";
import type { SentenceBreakdown } from "../lib/types";

interface Sentence {
  sentence_id: number;
  ja: string;
  furigana: string | null;
  en: string | null;
  tatoeba_id: number | null;
  new_word_id: string;
  new_word: string;
}

defineProps<{
  sentences: Sentence[];
  breakdowns: Record<string, SentenceBreakdown>;
  copy: Record<"title" | "intro" | "newWord" | "read" | "empty", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title">{{ copy.title }}</h1>
    <p class="muted mt-1 mb-5">{{ copy.intro }}</p>
    <ul class="space-y-3">
      <li v-for="sentence in sentences" :key="sentence.sentence_id" class="card border-l-4 border-l-amber">
        <ExampleSentence :example="sentence" :breakdown="breakdowns[sentence.ja]">
          <div class="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p class="text-sm">
              {{ copy.newWord }}:
              <a :href="`/kata/${sentence.new_word_id}`" class="rounded-md bg-lemon/60 px-1.5 py-0.5 font-bold no-underline">
                <JapaneseText :text="sentence.new_word" />
              </a>
              <template v-if="sentence.tatoeba_id">
                <span class="text-ink/50"> · </span>
                <a :href="`https://tatoeba.org/sentences/show/${sentence.tatoeba_id}`" rel="noopener" class="text-xs"
                  >Tatoeba #{{ sentence.tatoeba_id }}</a
                >
              </template>
            </p>
            <PostForm :action="`/bacaan/${sentence.sentence_id}/dibaca`">
              <button type="submit" class="btn-quiet">✓ {{ copy.read }}</button>
            </PostForm>
          </div>
        </ExampleSentence>
      </li>
      <li v-if="sentences.length === 0" class="alert">{{ copy.empty }}</li>
    </ul>
  </div>
</template>
