// The page's CSRF token, provided once by main.ts to every component that posts (forms and fetches).
import { type InjectionKey, inject } from "vue";

export const CSRF: InjectionKey<string> = Symbol("csrf");

export function useCsrf(): string {
  return inject(CSRF, "");
}
