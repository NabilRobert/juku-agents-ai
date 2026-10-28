// The quiz page's island: mounted only on /kuis, with the questions the server rendered.
import { createApp } from "vue";
import { pageCsrf, pageJson } from "../lib/http";
import QuizIsland from "./QuizIsland.vue";

const root = document.getElementById("quiz-island");
if (root) {
  createApp(QuizIsland, {
    quiz: pageJson("quiz-data"),
    copy: pageJson("quiz-copy"),
    csrf: pageCsrf(),
    moreUrl: root.dataset.moreUrl,
  }).mount(root);
}
