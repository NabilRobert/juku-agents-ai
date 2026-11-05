import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import Placement from "../src/pages/Placement.vue";
import { CSRF } from "../src/lib/csrf";

const question = (id: string) => ({ word_id: id, kind: "meaning" as const, prompt: id, options: ["a", "b"] });
const copy = new Proxy({}, { get: (_target, key) => String(key) }) as InstanceType<typeof Placement>["$props"]["copy"];

function mounted() {
  return mount(Placement, {
    props: { level: 5, nextLevel: 4, questions: [question("q1"), question("q2")], copy },
    global: { provide: { [CSRF as symbol]: "t" } },
  });
}

describe("Placement", () => {
  it("sends every answer, I don't know as empty, and offers the next level once passed", async () => {
    const result = { level: 5, correct: 1, total: 2, placed_through_unit_id: 45, passed_level: true };
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(result)));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mounted();
    await wrapper.findAll("button.option")[1]!.trigger("click");
    await wrapper.find("button.dont-know").trigger("click");
    await flushPromises();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/rencana/penempatan/5");
    expect(JSON.parse(String(init?.body)).answers.map((item: { chosen: string }) => item.chosen)).toEqual(["b", ""]);
    expect(wrapper.find('a[href="/rencana/penempatan?level=4"]').exists()).toBe(true);
    vi.unstubAllGlobals();
  });

  it("lets the learner send again when the server fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 500 })));
    const wrapper = mounted();
    await wrapper.find("button.dont-know").trigger("click");
    await wrapper.find("button.dont-know").trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    expect(wrapper.find("button.btn").text()).toBe("submit");
    vi.unstubAllGlobals();
  });
});
