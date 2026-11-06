// A button that marks something done without a reload (a word known, a grammar point understood, a
// sentence read): post it, remember it's done, and say so if it failed. Shared by the curriculum's pages.
import { reactive, ref } from "vue";
import { useCsrf } from "./csrf";
import { postJson } from "./http";

export function useAction() {
  const csrf = useCsrf();
  const pending = reactive(new Set<string>());
  const done = reactive(new Set<string>());
  const failed = ref(false);

  /** POST `url`; on success `key` counts as done. Returns whether it worked. */
  async function run(key: string, url: string): Promise<boolean> {
    if (pending.has(key) || done.has(key)) return false;
    pending.add(key);
    failed.value = false;
    const response = await postJson(url, {}, csrf).catch(() => null);
    pending.delete(key);
    if (!response?.ok) {
      failed.value = true;
      return false;
    }
    done.add(key);
    return true;
  }

  return { run, pending, done, failed };
}
