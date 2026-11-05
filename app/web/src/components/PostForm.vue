<script setup lang="ts">
// A plain form post with the page's CSRF token: the server's routes and redirects stay as they were.
import { useCsrf } from "../lib/csrf";

defineProps<{ action: string }>();
const csrf = useCsrf();
</script>

<template>
  <form method="post" :action="action">
    <input type="hidden" name="csrf" :value="csrf" />
    <slot />
  </form>
</template>
