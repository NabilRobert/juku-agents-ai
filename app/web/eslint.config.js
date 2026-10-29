// ESLint, for Arthur's lean-code limits only (CLAUDE.md, "Keep it lean"): complexity, function length and
// nesting. vue-tsc and Vitest already check types and behaviour, so no wider rule set is turned on here.
import vue from "eslint-plugin-vue";
import tseslint from "typescript-eslint";

const LIMITS = {
  complexity: ["error", 10],
  "max-depth": ["error", 3],
};

export default tseslint.config(
  { ignores: ["node_modules/**", "../src/juku_app/static/dist/**"] },
  ...vue.configs["flat/base"],
  { files: ["**/*.vue"], languageOptions: { parserOptions: { parser: tseslint.parser } } },
  { files: ["**/*.ts"], languageOptions: { parser: tseslint.parser } },
  {
    files: ["src/**/*.{ts,vue}", "scripts/**/*.mjs", "vite.config.ts"],
    rules: { ...LIMITS, "max-lines-per-function": ["error", { max: 40, skipBlankLines: true, skipComments: true }] },
  },
  // A Vitest file's describe() holds all its tests, so the function-length limit would only measure the file.
  { files: ["tests/**/*.ts"], rules: LIMITS },
);
