<script setup lang="ts">
// The frame around every page: the ink header with Juku's mark and, once signed in, the section tabs.
import type { Shell } from "../lib/types";

defineProps<{ shell: Shell }>();

function isCurrent(href: string): boolean {
  return window.location.pathname.startsWith(href);
}
</script>

<template>
  <header class="bg-ink text-white shadow-md">
    <div class="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3">
      <a :href="shell.signedIn ? '/beranda' : '/'" class="flex shrink-0 items-center gap-2 no-underline hover:text-white">
        <span lang="ja" class="grid size-9 place-items-center rounded-xl bg-amber text-xl font-black text-ink">塾</span>
        <span class="text-lg font-extrabold tracking-tight">Juku</span>
      </a>
      <nav v-if="shell.signedIn" class="-mx-1 flex min-w-0 gap-1 overflow-x-auto px-1 text-sm" aria-label="Juku">
        <a
          v-for="section in shell.sections"
          :key="section.slug"
          :href="`/${section.slug}`"
          :aria-current="shell.current === section.slug ? 'page' : undefined"
          class="shrink-0 rounded-full px-3 py-1.5 font-medium no-underline transition"
          :class="
            shell.current === section.slug
              ? 'bg-amber text-ink hover:text-ink'
              : 'text-white/80 hover:bg-white/10 hover:text-lemon'
          "
          >{{ section.label }}</a
        >
        <a
          v-for="link in shell.ownerLinks"
          :key="link.href"
          :href="link.href"
          class="owner-link shrink-0 rounded-full border border-orange/70 px-3 py-1.5 font-medium text-orange no-underline transition hover:bg-orange hover:text-ink"
          :class="{ 'bg-orange text-ink': isCurrent(link.href) }"
          >{{ link.label }}</a
        >
      </nav>
    </div>
    <div class="h-1 bg-linear-to-r from-lemon via-amber to-orange"></div>
  </header>
  <main class="mx-auto max-w-5xl px-4 py-6 sm:py-8"><slot /></main>
  <footer class="mx-auto max-w-5xl px-4 pb-8 text-xs">
    <a href="/tentang-data" class="text-ink/60">{{ shell.aboutData }}</a>
  </footer>
</template>
