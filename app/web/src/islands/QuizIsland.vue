<script setup lang="ts">
// The quiz (LE2, FE6): one question at a time, graded by the server, which looks the
// answer up again. The next batch of ten is fetched before this one runs out.
import { computed, ref } from "vue";
import { postJson } from "../lib/http";

interface QuizItem {
  word_id: string;
  kind: "meaning" | "reading";
  prompt: string;
  options: string[];
}
interface Verdict {
  is_correct: boolean;
  correct_option: string;
}

const props = defineProps<{
  quiz: { items: QuizItem[] };
  copy: { correct: string; wrong: string; next: string; done: string };
  csrf: string;
  moreUrl?: string;
}>();

const PREFETCH_WHEN_LEFT = 2;
const items = ref<QuizItem[]>([...props.quiz.items]);
const position = ref(0);
const verdict = ref<Verdict | null>(null);
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
  const response = await postJson("/kuis/jawab", { word_id: item.word_id, kind: item.kind, chosen: option }, props.csrf);
  verdict.value = (await response.json()) as Verdict;
  void prefetch();
}

function next(): void {
  verdict.value = null;
  position.value += 1;
}
</script>

<template>
  <section v-if="current" class="space-y-3">
    <p lang="ja" class="text-3xl">{{ current.prompt }}</p>
    <div class="grid gap-2">
      <button
        v-for="option in current.options"
        :key="option"
        class="option rounded border px-3 py-2 text-left"
        :disabled="verdict !== null"
        @click="choose(option)"
      >
        {{ option }}
      </button>
    </div>
    <p v-if="verdict" role="status">
      {{ verdict.is_correct ? copy.correct : `${copy.wrong} ${verdict.correct_option}` }}
    </p>
    <button v-if="verdict" class="next rounded border px-3 py-1" @click="next">{{ copy.next }}</button>
  </section>
  <p v-else role="status">{{ copy.done }}</p>
</template>
