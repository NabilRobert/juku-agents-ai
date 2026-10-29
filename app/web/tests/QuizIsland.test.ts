import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import QuizIsland from "../src/islands/QuizIsland.vue";

const copy = { correct: "Benar!", wrong: "Belum tepat. Jawabannya:", next: "Berikutnya", done: "Selesai" };
const quiz = {
  items: [
    { word_id: "w1", kind: "meaning" as const, prompt: "食べる", options: ["to drink", "to eat", "to see", "to go"] },
    { word_id: "w2", kind: "reading" as const, prompt: "水", options: ["みず", "ひ", "やま", "かわ"] },
  ],
};

describe("QuizIsland", () => {
  it("shows the first question and its four options", () => {
    const wrapper = mount(QuizIsland, { props: { quiz, copy, csrf: "t" } });
    expect(wrapper.text()).toContain("食べる");
    expect(wrapper.findAll("button.option")).toHaveLength(4);
  });

  it("sends the chosen option with the CSRF token and shows the server's verdict", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ is_correct: false, correct_option: "to eat" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(QuizIsland, { props: { quiz, copy, csrf: "t" } });
    await wrapper.findAll("button.option")[0]!.trigger("click");
    await flushPromises();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/kuis/jawab");
    expect((init as RequestInit).headers).toMatchObject({ "X-CSRF-Token": "t" });
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ word_id: "w1", kind: "meaning", chosen: "to drink" });
    expect(wrapper.text()).toContain("Belum tepat. Jawabannya: to eat");
    vi.unstubAllGlobals();
  });

  it("moves on, and says it's done after the last question", async () => {
    // A fresh response each call: a body can be read only once.
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ is_correct: true, correct_option: "x" }))));
    const wrapper = mount(QuizIsland, { props: { quiz, copy, csrf: "t" } });
    for (let index = 0; index < 2; index += 1) {
      await wrapper.findAll("button.option")[1]!.trigger("click");
      await flushPromises();
      await wrapper.find("button.next").trigger("click");
    }
    expect(wrapper.text()).toContain("Selesai");
    vi.unstubAllGlobals();
  });
});
