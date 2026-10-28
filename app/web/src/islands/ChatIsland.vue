<script setup lang="ts">
// Chat with Shiori (AG5): the answer streams in as it's written (server-sent events),
// then shows whether its citations checked out, and can be rated (UI3).
import { ref } from "vue";
import { postJson } from "../lib/http";
import { readEvents } from "../lib/sse";

interface Done {
  is_verified: boolean;
  stopped_because: string | null;
  message_id: number | null;
}

const props = defineProps<{
  copy: { placeholder: string; send: string; unverified: string; helpful: string; unhelpful: string };
  csrf: string;
}>();

const question = ref("");
const answer = ref("");
const done = ref<Done | null>(null);
const busy = ref(false);
const rated = ref(false);

async function send(): Promise<void> {
  if (!question.value.trim() || busy.value) return;
  busy.value = true;
  answer.value = "";
  done.value = null;
  rated.value = false;
  try {
    const response = await postJson("/chat/kirim", { question: question.value }, props.csrf);
    for await (const event of readEvents(response)) {
      if (event.event === "delta") answer.value += event.data;
      if (event.event === "done") done.value = JSON.parse(event.data) as Done;
    }
  } finally {
    busy.value = false;
  }
}

async function rate(isHelpful: boolean): Promise<void> {
  if (!done.value?.message_id) return;
  await postJson(
    "/nilai",
    { target_kind: "chat", target_id: done.value.message_id, is_helpful: isHelpful, reason: null, may_quote: false },
    props.csrf,
  );
  rated.value = true;
}
</script>

<template>
  <form class="space-y-2" @submit.prevent="send">
    <textarea v-model="question" :placeholder="copy.placeholder" rows="3" class="w-full rounded border p-2" />
    <button type="submit" class="rounded border px-3 py-1" :disabled="busy">{{ copy.send }}</button>
  </form>
  <article v-if="answer || done" class="mt-3 space-y-1" aria-live="polite">
    <p>{{ answer }}</p>
    <p v-if="done && !done.is_verified" class="text-xs text-amber-700">{{ copy.unverified }}</p>
    <div v-if="done?.message_id && !rated" class="flex gap-2 text-sm">
      <button class="helpful underline" @click="rate(true)">{{ copy.helpful }}</button>
      <button class="unhelpful underline" @click="rate(false)">{{ copy.unhelpful }}</button>
    </div>
  </article>
</template>
