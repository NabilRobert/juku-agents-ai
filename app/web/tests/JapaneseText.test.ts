import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import JapaneseText from "../src/components/JapaneseText.vue";
import { furiganaRuns } from "../src/lib/furigana";
import { STUDY } from "../src/lib/study";

const study = {
  explain: "Jelaskan",
  hide: "Tutup",
  words: "Kata",
  grammar: "Tata bahasa",
  grammarNote: "",
  known: "sudah tahu",
  kanjiWords: "Kata dengan kanji ini",
  strokes: "goresan",
  loading: "Memuat…",
  notKanji: "Tidak ada detail.",
};
const sei = {
  character: "生",
  level: 5,
  strokes: 5,
  onyomi: ["セイ", "ショウ"],
  kunyomi: ["い.きる"],
  meanings: ["life", "birth"],
  words: [{ word_id: "w1", word: "先生", reading: "せんせい", level: 5, meaning: "teacher", is_known: true }],
};

function mounted(text: string, furigana: string | null = null) {
  return mount(JapaneseText, { props: { text, furigana }, global: { provide: { [STUDY as symbol]: study } } });
}

describe("furiganaRuns", () => {
  it("splits {kanji|reading} from the plain text around it", () => {
    expect(furiganaRuns("私は学生", "{私|わたし}は{学生|がくせい}")).toEqual([
      { text: "私", reading: "わたし" },
      { text: "は", reading: null },
      { text: "学生", reading: "がくせい" },
    ]);
  });

  it("keeps the text whole when there's no furigana", () => {
    expect(furiganaRuns("こんにちは", null)).toEqual([{ text: "こんにちは", reading: null }]);
  });
});

describe("JapaneseText", () => {
  it("draws furigana as ruby and makes only the kanji hoverable", () => {
    const wrapper = mounted("先生です", "{先生|せんせい}です");
    expect(wrapper.find("rt").text()).toBe("せんせい");
    expect(wrapper.findAll(".kanji").map((kanji) => kanji.text())).toEqual(["先", "生"]);
  });

  it("shows a kanji's readings and the words that use it, asking the server once", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(sei)));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mounted("生生");
    const [first, second] = wrapper.findAll(".kanji");
    await first!.trigger("mouseenter");
    await second!.trigger("mouseenter");
    await flushPromises();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(`/kanji/${encodeURIComponent("生")}`);
    const popup = wrapper.find('[role="tooltip"]');
    expect(popup.text()).toContain("セイ、ショウ");
    expect(popup.text()).toContain("先生");
    expect(popup.text()).toContain("✓ sudah tahu");
    vi.unstubAllGlobals();
  });
});
