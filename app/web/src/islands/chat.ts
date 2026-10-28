// The chat page's island: mounted only on /chat.
import { createApp } from "vue";
import { pageCsrf, pageJson } from "../lib/http";
import ChatIsland from "./ChatIsland.vue";

const root = document.getElementById("chat-island");
if (root) {
  createApp(ChatIsland, { copy: pageJson("chat-copy"), csrf: pageCsrf() }).mount(root);
}
