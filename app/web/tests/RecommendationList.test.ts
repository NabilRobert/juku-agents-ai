import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import RecommendationList from "../src/components/RecommendationList.vue";
import { CSRF } from "../src/lib/csrf";
import { STUDY } from "../src/lib/study";

const word = (id: string) => ({ word_id: id, word: id, reading: id, level: 5, meanings: ["m"], reason: "r" });
const copy = { iKnowThis: "Saya tahu", examples: "Contoh", failed: "Gagal" };

function mounted() {
  return mount(RecommendationList, {
    props: { words: [word("a"), word("b"), word("c")], copy },
    global: { provide: { [CSRF as symbol]: "t", [STUDY as symbol]: {} } },
  });
}

const shownIds = (wrapper: ReturnType<typeof mounted>) => wrapper.findAll("li").map((li) => li.find("p").text());

describe("RecommendationList", () => {
  it("removes the marked card, keeps the others' order and adds the next one at the end", async () => {
    // The server's new order differs (c first): the cards already shown don't move.
    const reply = { known_words: 4, words: [word("c"), word("b"), word("d")] };
    const fetchMock = vi.fn(async (_url: string) => new Response(JSON.stringify(reply)));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mounted();
    await wrapper.findAll("button.known")[0]!.trigger("click");
    await flushPromises();
    expect(fetchMock.mock.calls[0]![0]).toBe("/rekomendasi/a/dikuasai");
    expect(shownIds(wrapper)).toEqual(["b", "c", "d"]);
    expect(wrapper.emitted("known")).toEqual([[4]]);
    vi.unstubAllGlobals();
  });

  it("keeps the card and says so when marking fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 500 })));
    const wrapper = mounted();
    await wrapper.findAll("button.known")[1]!.trigger("click");
    await flushPromises();
    expect(shownIds(wrapper)).toEqual(["a", "b", "c"]);
    expect(wrapper.find('[role="alert"]').text()).toBe("Gagal");
    vi.unstubAllGlobals();
  });
});
