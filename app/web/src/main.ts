// The one entry every page loads (ADR-024, revised 2026-11-05): it reads the data the server put in the page
// (base.html's shell-data, the page template's page-data), loads only that page's component, and mounts it
// inside the shared shell. The server keeps the data, the translations and the forms.
import { type Component, createApp, h } from "vue";
import AppShell from "./components/AppShell.vue";
import { CSRF } from "./lib/csrf";
import { STUDY } from "./lib/study";
import { pageJson } from "./lib/http";
import type { PageData, Shell } from "./lib/types";

const pages = import.meta.glob<{ default: Component }>("./pages/*.vue");

async function mount(): Promise<void> {
  const shell = pageJson<Shell>("shell-data");
  const data = pageJson<PageData>("page-data");
  const load = pages[`./pages/${data.component}.vue`];
  if (!load) throw new Error(`No page component "${data.component}": add app/web/src/pages/${data.component}.vue`);
  const page = (await load()).default;
  createApp({ render: () => h(AppShell, { shell }, () => h(page, data.props)) })
    .provide(CSRF, shell.csrf)
    .provide(STUDY, shell.study)
    .mount("#app");
}

void mount();
