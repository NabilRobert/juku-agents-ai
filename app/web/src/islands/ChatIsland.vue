<script setup lang="ts">
// Chat with Shiori (AG5): the answer streams in as it's written (server-sent events),
// then shows whether its citations checked out, and can be rated (UI3).
import { ref } from "vue";
import { postJson } from "../lib/http";
import { readEvents } from "../lib/sse";
import type { ChatCopy } from "../lib/types";

interface Done {
  is_verified: boolean;
  stopped_because: string | null;
  message_id: number | null;
}

const props = defineProps<{
  copy: ChatCopy;
  csrf: string;
}>();

const question = ref("");
const asked = ref("");
const answer = ref("");
const done = ref<Done | null>(null);
const busy = ref(false);
const rated = ref(false);
const failed = ref(false);

async function readAnswer(text: string): Promise<void> {
  const response = await postJson("/chat/kirim", { question: text }, props.csrf);
  for await (const event of readEvents(response)) {
    if (event.event === "delta") answer.value += event.data;
    if (event.event === "done") done.value = JSON.parse(event.data) as Done;
  }
}

async function send(): Promise<void> {
  if (!question.value.trim() || busy.value) return;
  busy.value = true;
  asked.value = question.value;
  question.value = "";
  answer.value = "";
  done.value = null;
  rated.value = false;
  failed.value = false;
  try {
    await readAnswer(asked.value);
  } catch {
    // Handled below: a dropped connection looks the same as a stream with no last event.
  }
  // The server ends every turn it can with `done`, so without one, it's the connection or the page's session.
  failed.value = done.value === null;
  busy.value = false;
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
  <div class="flex flex-col gap-2">
    <p v-if="asked" class="max-w-[85%] self-end rounded-2xl rounded-br-sm bg-ink px-4 py-2.5 whitespace-pre-line text-white shadow-sm">
      {{ asked }}
    </p>
    <article
      v-if="answer || done || busy"
      class="max-w-[85%] space-y-2 self-start rounded-2xl rounded-bl-sm border border-gold/40 bg-white px-4 py-2.5 shadow-sm"
      aria-live="polite"
    >
      <p class="whitespace-pre-line">{{ answer }}<span v-if="busy && !answer" class="animate-pulse">…</span></p>
      <p v-if="done && !done.is_verified" class="text-xs font-semibold text-amber-700">{{ copy.unverified }}</p>
      <div v-if="done?.message_id && !rated" class="flex gap-2">
        <button class="helpful btn-quiet py-1" @click="rate(true)">👍 {{ copy.helpful }}</button>
        <button class="unhelpful btn-quiet py-1" @click="rate(false)">👎 {{ copy.unhelpful }}</button>
      </div>
    </article>
    <p v-if="failed" class="alert" role="alert">{{ copy.failed }}</p>
  </div>
  <form class="card sticky bottom-3 mt-4 flex items-end gap-2 p-3" @submit.prevent="send">
    <textarea
      v-model="question"
      :placeholder="copy.placeholder"
      rows="2"
      class="field resize-none"
      @keydown.enter.exact.prevent="send"
    />
    <button type="submit" class="btn shrink-0" :disabled="busy">{{ copy.send }}</button>
  </form>
</template>
