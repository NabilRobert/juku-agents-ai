<script setup lang="ts">
// The home page's recommendations. "I know this word" marks it without a reload: its card fades out, the
// cards after it slide into its place, and the next recommendation joins at the end. The cards already
// shown keep their order, so nothing jumps around (the recommender may reorder once a word is known).
import { ref } from "vue";
import { useCsrf } from "../lib/csrf";
import { postJson } from "../lib/http";
import type { Word } from "../lib/types";
import WordCard from "./WordCard.vue";

const props = defineProps<{ words: Word[]; copy: Record<"iKnowThis" | "examples" | "failed", string> }>();
const emit = defineEmits<{ known: [count: number] }>();
const csrf = useCsrf();

const shown = ref<Word[]>([...props.words]);
const pending = ref(new Set<string>());
const failed = ref(false);

/** The cards still shown, in their order, then any new recommendations, up to as many as the server gives. */
function merged(current: Word[], marked: string, fresh: Word[]): Word[] {
  const kept = current.filter((word) => word.word_id !== marked);
  const keptIds = new Set(kept.map((word) => word.word_id));
  const added = fresh.filter((word) => !keptIds.has(word.word_id) && word.word_id !== marked);
  return [...kept, ...added].slice(0, Math.max(fresh.length, kept.length));
}

async function markKnown(word: Word): Promise<void> {
  if (pending.value.has(word.word_id)) return;
  pending.value.add(word.word_id);
  failed.value = false;
  const response = await postJson(`/rekomendasi/${encodeURIComponent(word.word_id)}/dikuasai`, {}, csrf).catch(() => null);
  pending.value.delete(word.word_id);
  if (!response?.ok) {
    failed.value = true;
    return;
  }
  const result = (await response.json()) as { known_words: number; words: Word[] };
  shown.value = merged(shown.value, word.word_id, result.words);
  emit("known", result.known_words);
}
</script>

<template>
  <p v-if="failed" class="alert mb-3" role="alert">{{ copy.failed }}</p>
  <TransitionGroup tag="ol" name="card" class="relative grid gap-3 sm:grid-cols-2">
    <li v-for="word in shown" :key="word.word_id" class="recommendation flex">
      <WordCard :word="word" :examples-label="copy.examples" class="w-full">
        <template #action>
          <button
            type="button"
            class="known btn-quiet w-full"
            :disabled="pending.has(word.word_id)"
            @click="markKnown(word)"
          >
            ✓ {{ copy.iKnowThis }}
          </button>
        </template>
      </WordCard>
    </li>
  </TransitionGroup>
</template>

<style scoped>
/* The marked card fades and shrinks; the others glide into place; the new one fades in. */
.card-move,
.card-enter-active,
.card-leave-active {
  transition:
    transform 0.35s ease,
    opacity 0.3s ease;
}
.card-enter-from,
.card-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
/* Out of the grid's flow while it fades, so the cards after it can move up at once. */
.card-leave-active {
  position: absolute;
  width: calc(50% - 0.375rem);
}
@media (max-width: 639px) {
  .card-leave-active {
    width: 100%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .card-move,
  .card-enter-active,
  .card-leave-active {
    transition: none;
  }
}
</style>
