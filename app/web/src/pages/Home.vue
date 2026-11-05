<script setup lang="ts">
// Beranda: the words the learner knows, and the next words worth learning (the recommender's order).
import JapaneseText from "../components/JapaneseText.vue";
import PostForm from "../components/PostForm.vue";
import type { Word } from "../lib/types";

defineProps<{
  nickname: string;
  knownWords: number;
  words: Word[];
  copy: Record<"hello" | "wordsYouKnow" | "recommendations" | "iKnowThis" | "quiz" | "reading" | "plan" | "examples", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <section class="relative overflow-hidden rounded-3xl bg-linear-to-br from-lemon via-amber to-orange p-6 shadow-md sm:p-8">
      <span lang="ja" aria-hidden="true" class="pointer-events-none absolute -top-6 -right-2 text-[9rem] leading-none font-black text-ink/10">塾</span>
      <h1 class="page-title">{{ copy.hello }}, {{ nickname }}</h1>
      <p class="mt-4 text-sm font-semibold tracking-wide text-ink/70 uppercase">{{ copy.wordsYouKnow }}</p>
      <p class="text-5xl font-black">{{ knownWords }}</p>
      <div class="mt-5 flex flex-wrap gap-2">
        <a href="/kuis" class="btn bg-ink text-lemon hover:bg-ink/85 hover:text-lemon">{{ copy.quiz }}</a>
        <a href="/bacaan" class="btn-quiet">{{ copy.reading }}</a>
        <a href="/rencana" class="btn-quiet">{{ copy.plan }}</a>
      </div>
    </section>

    <h2 class="section-title mt-8 mb-3">{{ copy.recommendations }}</h2>
    <ol class="grid gap-3 sm:grid-cols-2">
      <li v-for="word in words" :key="word.word_id" class="card flex flex-col gap-2">
        <div class="flex items-start justify-between gap-2">
          <div>
            <p class="text-3xl leading-tight font-bold"><JapaneseText :text="word.word" /></p>
            <p lang="ja" class="muted">{{ word.reading }}</p>
          </div>
          <span class="chip">N{{ word.level }}</span>
        </div>
        <p class="font-medium">
          {{ word.meanings.slice(0, 2).join("; ") }}
          <a :href="`/kata/${word.word_id}`" class="ml-1 text-sm whitespace-nowrap">{{ copy.examples }} →</a>
        </p>
        <p class="muted">{{ word.reason }}</p>
        <PostForm :action="`/kata/${word.word_id}/dikuasai`" class="mt-auto pt-1">
          <button type="submit" class="btn-quiet w-full">✓ {{ copy.iKnowThis }}</button>
        </PostForm>
      </li>
    </ol>
  </div>
</template>
