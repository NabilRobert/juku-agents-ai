<script setup lang="ts">
// The placement test (engine/placement.py): one level's questions, one at a time, without showing the answers
// (a placement test, not a lesson). "I don't know" counts as wrong, which beats a lucky guess placing a learner
// past what they know. At the end the answers go to the server, which places the learner and says where.
import { computed, ref } from "vue";
import ProgressBar from "../components/ProgressBar.vue";
import QuizQuestion from "../components/QuizQuestion.vue";
import { useCsrf } from "../lib/csrf";
import { postJson } from "../lib/http";
import type { PlacementResult, QuizItem } from "../lib/types";

type PlacementCopy =
  | "title" | "explain" | "dontKnow" | "question" | "submit" | "passed" | "placedThrough" | "notPlaced"
  | "nextLevel" | "toCurriculum" | "correct" | "failed";

const props = defineProps<{ level: number; nextLevel: number | null; questions: QuizItem[]; copy: Record<PlacementCopy, string> }>();
const csrf = useCsrf();
const answers = ref<string[]>([]);
const result = ref<PlacementResult | null>(null);
const isSending = ref(false);
const failed = ref(false);

const current = computed(() => props.questions[answers.value.length]);

async function send(): Promise<void> {
  isSending.value = true;
  failed.value = false;
  const body = {
    answers: props.questions.map((item, index) => ({ word_id: item.word_id, kind: item.kind, chosen: answers.value[index] ?? "" })),
  };
  const response = await postJson(`/rencana/penempatan/${props.level}`, body, csrf).catch(() => null);
  isSending.value = false;
  if (!response?.ok) {
    failed.value = true;
    return;
  }
  result.value = (await response.json()) as PlacementResult;
}

function answer(option: string): void {
  answers.value.push(option);
  if (answers.value.length === props.questions.length) void send();
}
</script>

<template>
  <div class="mx-auto max-w-2xl space-y-6">
    <section class="card space-y-2">
      <h1 class="page-title"><span class="chip mr-2 align-middle">N{{ level }}</span>{{ copy.title }}</h1>
      <p class="muted">{{ copy.explain }}</p>
      <ProgressBar :value="answers.length" :total="questions.length" :label="copy.question" />
    </section>

    <section v-if="result" class="card space-y-3" role="status">
      <p class="text-2xl font-bold">{{ result.correct }} / {{ result.total }} {{ copy.correct }}</p>
      <p v-if="result.passed_level" class="font-semibold">✓ {{ copy.passed }}</p>
      <p v-else-if="result.placed_through_unit_id">{{ copy.placedThrough }} {{ result.placed_through_unit_id }}</p>
      <p v-else>{{ copy.notPlaced }}</p>
      <p class="flex flex-wrap gap-2">
        <a v-if="result.passed_level && nextLevel" :href="`/rencana/penempatan?level=${nextLevel}`" class="btn">{{ copy.nextLevel }} (N{{ nextLevel }})</a>
        <a href="/rencana" class="btn-quiet">{{ copy.toCurriculum }}</a>
      </p>
    </section>
    <template v-else-if="current">
      <section class="card">
        <QuizQuestion :item="current" @choose="answer" />
        <p class="mt-4 text-center">
          <button type="button" class="dont-know btn-quiet" @click="answer('')">{{ copy.dontKnow }}</button>
        </p>
      </section>
    </template>
    <section v-else class="card space-y-2">
      <p v-if="failed" class="alert" role="alert">{{ copy.failed }}</p>
      <button type="button" class="btn" :disabled="isSending" @click="send">{{ copy.submit }}</button>
    </section>
  </div>
</template>
