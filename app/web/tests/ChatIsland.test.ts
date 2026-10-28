import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ChatIsland from "../src/islands/ChatIsland.vue";

const copy = { placeholder: "Tulis pertanyaanmu", send: "Kirim", unverified: "belum terverifikasi", helpful: "Membantu", unhelpful: "Tidak membantu" };

function stream(text: string): Response {
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
  return new Response(body, { headers: { "content-type": "text/event-stream" } });
}

describe("ChatIsland", () => {
  it("streams the answer piece by piece and labels an unverified one", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      stream('event: delta\r\ndata: Pelajari \r\n\r\nevent: delta\r\ndata: 食べる.\r\n\r\nevent: done\r\ndata: {"is_verified": false, "stopped_because": null, "message_id": 7}\r\n\r\n'),
    );
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ChatIsland, { props: { copy, csrf: "t" } });
    await wrapper.find("textarea").setValue("kata apa?");
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Pelajari 食べる.");
    expect(wrapper.text()).toContain("belum terverifikasi");
    expect(fetchMock.mock.calls[0]![0]).toBe("/chat/kirim");
    vi.unstubAllGlobals();
  });

  it("rates an answer by its message ID", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(stream('event: done\r\ndata: {"is_verified": true, "stopped_because": null, "message_id": 9}\r\n\r\n'))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ChatIsland, { props: { copy, csrf: "t" } });
    await wrapper.find("textarea").setValue("?");
    await wrapper.find("form").trigger("submit");
    await flushPromises();
    await wrapper.find("button.unhelpful").trigger("click");
    const [url, init] = fetchMock.mock.calls[1]!;
    expect(url).toBe("/nilai");
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({ target_kind: "chat", target_id: 9, is_helpful: false });
    vi.unstubAllGlobals();
  });
});
