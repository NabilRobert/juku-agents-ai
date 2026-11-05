<script setup lang="ts">
// Today's lesson on Home (engine/curriculum.py: today_plan): the current unit's next words, one grammar
// point, a few sentences and the quiz, each with its target and what's done today. Following it is the plan.
import { computed } from "vue";
import { useAction } from "../lib/action";
import type { TodayPlan } from "../lib/types";
import ProgressBar from "./ProgressBar.vue";

type TodayCopy =
  | "title" | "unit" | "newWords" | "grammar" | "sentences" | "reviews" | "quiz" | "allDone" | "finished"
  | "continue" | "understand" | "toQuiz";

const props = defineProps<{ today: TodayPlan; copy: Record<TodayCopy, string> }>();
const { run, pending, done } = useAction();

const grammarKey = computed(() => `grammar:${props.today.grammar?.grammar_id ?? ""}`);
const grammarDone = computed(() => props.today.grammar_done + (done.has(grammarKey.value) ? 1 : 0));
const isAllDone = computed(
  () =>
    props.today.words_done >= props.today.words_target &&
    props.today.sentences_done >= props.today.sentences_target &&
    props.today.quiz_done >= props.today.quiz_target &&
    (props.today.grammar === null || done.has(grammarKey.value)),
);
</script>

<template>
  <section class="today card space-y-4 border-orange/50">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 class="section-title">{{ copy.title }}</h2>
      <a v-if="today.unit" :href="`/rencana/unit/${today.unit.unit_id}`" class="chip no-underline">
        N{{ today.unit.level }} · {{ copy.unit }} {{ today.unit.number }}
      </a>
    </div>
    <p v-if="!today.unit" class="font-semibold">🎉 {{ copy.finished }}</p>
    <template v-else>
      <p v-if="isAllDone" class="font-semibold" role="status">✓ {{ copy.allDone }}</p>
      <div class="grid gap-3 sm:grid-cols-2">
        <ProgressBar :value="today.words_done" :total="today.words_target" :label="copy.newWords" />
        <ProgressBar :value="today.quiz_done" :total="today.quiz_target" :label="copy.quiz" tone="gold" />
        <ProgressBar :value="today.sentences_done" :total="today.sentences_target" :label="copy.sentences" />
        <ProgressBar v-if="today.grammar" :value="Math.min(1, grammarDone)" :total="1" :label="copy.grammar" tone="gold" />
      </div>
      <p v-if="today.new_words.length" class="flex flex-wrap gap-2" lang="ja">
        <a v-for="word in today.new_words" :key="word.word_id" :href="`/kata/${word.word_id}`" class="chip no-underline">
          <span class="font-bold">{{ word.word }}</span>&nbsp;<span class="text-ink/60">{{ word.reading }}</span>
        </a>
      </p>
      <div v-if="today.grammar" class="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-lemon/40 p-3">
        <a :href="`/tata-bahasa/${today.grammar.grammar_id}`" class="no-underline">
          <span lang="ja" class="font-bold">{{ today.grammar.pattern }}</span>
          <span class="muted ml-2">{{ today.grammar.meaning }}</span>
        </a>
        <span v-if="done.has(grammarKey)" class="chip bg-lemon text-ink">✓</span>
        <button v-else type="button" class="understand btn-quiet py-1 text-sm" :disabled="pending.has(grammarKey)"
          @click="run(grammarKey, `/rencana/tata-bahasa/${encodeURIComponent(today.grammar.grammar_id)}/paham`)">
          {{ copy.understand }}
        </button>
      </div>
      <p v-if="today.reviews_due" class="muted text-sm">{{ today.reviews_due }} {{ copy.reviews }}</p>
      <p class="flex flex-wrap gap-2">
        <a :href="`/rencana/unit/${today.unit.unit_id}`" class="btn">{{ copy.continue }} →</a>
        <a href="/kuis" class="btn-quiet">{{ copy.toQuiz }}</a>
      </p>
    </template>
  </section>
</template>
