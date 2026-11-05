<script setup lang="ts">
// Persetujuan: the versioned notice (rendered by the server from consent/<version>.html), then the four choices.
import PostForm from "../components/PostForm.vue";

type ChoiceKey = "isAdult" | "acceptsService" | "acceptsAggregates" | "acceptsGroupDigest";

defineProps<{
  noticeHtml: string;
  version: string;
  hasError: boolean;
  copy: Record<ChoiceKey | "title" | "error" | "agree" | "noticeVersion", string>;
}>();

// The form field each choice posts, as the server's consent route reads them.
const CHOICES: { name: string; key: ChoiceKey }[] = [
  { name: "is_adult", key: "isAdult" },
  { name: "accepts_service", key: "acceptsService" },
  { name: "accepts_aggregates", key: "acceptsAggregates" },
  { name: "accepts_group_digest", key: "acceptsGroupDigest" },
];
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="page-title mb-4">{{ copy.title }}</h1>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div class="card leading-relaxed" v-html="noticeHtml"></div>
    <p v-if="hasError" role="alert" class="alert mt-4">{{ copy.error }}</p>
    <PostForm action="/persetujuan" class="card mt-4 space-y-3">
      <label v-for="choice in CHOICES" :key="choice.name" class="flex gap-3">
        <input type="checkbox" :name="choice.name" class="mt-1 size-4 shrink-0 accent-orange" />
        <span>{{ copy[choice.key] }}</span>
      </label>
      <button type="submit" class="btn mt-2">{{ copy.agree }}</button>
    </PostForm>
    <p class="muted mt-3 text-xs">{{ copy.noticeVersion }} {{ version }}</p>
  </div>
</template>
