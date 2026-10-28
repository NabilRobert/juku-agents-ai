<script setup lang="ts">
// Stub until the memory page lands (EDD1): the tests in tests/MemoryIsland.test.ts describe it.
import type { KnownWord, MemoryCopy, MemoryNote } from "./memory-types";

defineProps<{ notes: MemoryNote[]; words: KnownWord[]; copy: MemoryCopy; csrf: string }>();
</script>

<template>
  <div></div>
</template>
