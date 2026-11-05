<script setup lang="ts">
// ID | EN: posts the choice to /bahasa, which keeps it in the session and comes back to this same page.
import PostForm from "./PostForm.vue";

defineProps<{ language: "id" | "en"; label: string }>();
const back = window.location.pathname + window.location.search;
const LANGUAGES = [
  { code: "id", name: "ID" },
  { code: "en", name: "EN" },
] as const;
</script>

<template>
  <PostForm action="/bahasa" class="ml-auto flex shrink-0 overflow-hidden rounded-full border border-white/30 text-xs font-bold" :aria-label="label">
    <input type="hidden" name="back" :value="back" />
    <button
      v-for="choice in LANGUAGES"
      :key="choice.code"
      type="submit"
      name="language"
      :value="choice.code"
      :aria-pressed="language === choice.code"
      class="language cursor-pointer px-2.5 py-1 transition"
      :class="language === choice.code ? 'bg-lemon text-ink' : 'text-white/70 hover:text-lemon'"
    >
      {{ choice.name }}
    </button>
  </PostForm>
</template>
