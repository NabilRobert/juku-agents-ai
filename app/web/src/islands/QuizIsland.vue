<script setup lang="ts">
// The quiz (LE2, FE6): one question at a time, graded by the server, which looks the
// answer up again. The next batch of ten is fetched before this one runs out.
import { computed, ref } from "vue";
import { postJson } from "../lib/http";
import type { QuizCopy, QuizItem } from "../lib/types";

interface Verdict {
  is_correct: boolean;
  correct_option: string;
}

const props = defineProps<{
  quiz: { items: QuizItem[] };
  copy: QuizCopy;
  csrf: string;
  moreUrl?: string;
}>();

const PREFETCH_WHEN_LEFT = 2;
const items = ref<QuizItem[]>([...props.quiz.items]);
const position = ref(0);
const verdict = ref<Verdict | null>(null);
const chosen = ref<string | null>(null);
const batch = ref(1);
const current = computed(() => items.value[position.value]);

async function prefetch(): Promise<void> {
  if (!props.moreUrl || items.value.length - position.value > PREFETCH_WHEN_LEFT) return;
  const response = await fetch(`${props.moreUrl}?batch=${batch.value}`);
  if (!response.ok) return;
  batch.value += 1;
  items.value.push(...((await response.json()) as { items: QuizItem[] }).items);
}

async function choose(option: string): Promise<void> {
  const item = current.value;
  if (!item || verdict.value) return;
  chosen.value = option;
  const response = await postJson("/kuis/jawab", { word_id: item.word_id, kind: item.kind, chosen: option }, props.csrf);
  verdict.value = (await response.json()) as Verdict;
  void prefetch();
}

function next(): void {
  verdict.value = null;
  chosen.value = null;
  position.value += 1;
}

/** How an option looks: plain while answering; afterwards the right one in yellow, a wrong pick struck out. */
function optionLook(option: string): string {
  if (!verdict.value) return "border-ink/15 bg-white hover:border-orange hover:bg-lemon/30";
  if (option === verdict.value.correct_option) return "border-gold bg-lemon font-bold";
  if (option === chosen.value) return "border-ink/15 bg-ink/5 text-ink/50 line-through";
  return "border-ink/10 bg-white text-ink/50";
}
</script>

<template>
  <section v-if="current" class="space-y-5">
    <p class="muted text-center text-xs tracking-widest uppercase">{{ position + 1 }}</p>
    <p lang="ja" class="text-center text-5xl font-bold sm:text-6xl">{{ current.prompt }}</p>
    <div class="grid gap-2 sm:grid-cols-2">
      <button
        v-for="option in current.options"
        :key="option"
        class="option rounded-2xl border-2 px-4 py-3 text-left text-lg transition disabled:cursor-default"
        :class="optionLook(option)"
        :disabled="verdict !== null"
        @click="choose(option)"
      >
        {{ option }}
      </button>
    </div>
    <div v-if="verdict" class="flex flex-wrap items-center justify-between gap-3 rounded-2xl px-4 py-3" :class="verdict.is_correct ? 'bg-lemon/60' : 'bg-orange/20'">
      <p role="status" class="font-semibold">
        {{ verdict.is_correct ? `✓ ${copy.correct}` : `${copy.wrong} ${verdict.correct_option}` }}
      </p>
      <button class="next btn" @click="next">{{ copy.next }} →</button>
    </div>
  </section>
  <p v-else role="status" class="py-10 text-center text-xl font-bold">🎉 {{ copy.done }}</p>
</template>
