<script setup lang="ts">
// Chat: earlier messages as bubbles, then the chat island for the next question.
import ChatIsland from "../islands/ChatIsland.vue";
import { useCsrf } from "../lib/csrf";
import type { ChatCopy } from "../lib/types";

defineProps<{
  title: string;
  history: { role: string; body: string; is_verified: boolean }[];
  copy: ChatCopy;
}>();
const csrf = useCsrf();
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title mb-4">{{ title }}</h1>
    <ul id="chat-history" class="mb-4 flex flex-col gap-2">
      <li
        v-for="(message, index) in history"
        :key="index"
        :data-role="message.role"
        class="max-w-[85%] rounded-2xl px-4 py-2.5 whitespace-pre-line shadow-sm"
        :class="
          message.role === 'shiori'
            ? 'self-start rounded-bl-sm border border-gold/40 bg-white'
            : 'self-end rounded-br-sm bg-ink text-white'
        "
      >
        {{ message.body }}
        <span v-if="message.role === 'shiori' && !message.is_verified" class="mt-1 block text-xs font-semibold text-amber-700">
          {{ copy.unverified }}
        </span>
      </li>
    </ul>
    <ChatIsland :copy="copy" :csrf="csrf" />
  </div>
</template>
