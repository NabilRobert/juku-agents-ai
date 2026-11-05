<script setup lang="ts">
// Mulai: the few details a new learner gives after consenting.
import PostForm from "../components/PostForm.vue";

defineProps<{
  levels: number[];
  timezones: string[];
  copy: Record<"title" | "nickname" | "targetLevel" | "timeZone" | "examDate" | "start", string>;
}>();
</script>

<template>
  <div class="mx-auto max-w-md">
    <h1 class="page-title mb-4">{{ copy.title }}</h1>
    <PostForm action="/mulai" class="card space-y-4">
      <label class="block">
        <span class="label">{{ copy.nickname }}</span>
        <input name="nickname" maxlength="30" required class="field" />
      </label>
      <label class="block">
        <span class="label">{{ copy.targetLevel }}</span>
        <select name="target_level" class="field">
          <option v-for="level in levels" :key="level" :value="level">N{{ level }}</option>
        </select>
      </label>
      <label class="block">
        <span class="label">{{ copy.timeZone }}</span>
        <select name="timezone" class="field">
          <option v-for="zone in timezones" :key="zone" :value="zone">{{ zone }}</option>
        </select>
      </label>
      <label class="block">
        <span class="label">{{ copy.examDate }}</span>
        <input type="date" name="exam_date" class="field" />
      </label>
      <button type="submit" class="btn w-full">{{ copy.start }}</button>
    </PostForm>
  </div>
</template>
