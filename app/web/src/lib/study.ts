// The study components' shared text (base.html's shell data), provided once by main.ts.
import { type InjectionKey, inject } from "vue";
import type { StudyCopy } from "./types";

export const STUDY: InjectionKey<StudyCopy> = Symbol("study");

export function useStudyCopy(): StudyCopy {
  const copy = inject(STUDY);
  if (!copy) throw new Error("no study copy: main.ts provides it from base.html's shell-data");
  return copy;
}
