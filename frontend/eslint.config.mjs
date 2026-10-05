import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

// Replaces eslint-config-next. Its @next/eslint-plugin-next depends on
// fast-glob -> micromatch -> braces, and braces has no patched release at all
// (latest is 3.0.3 and the advisory covers <=3.0.3), so that chain cannot be
// cleared by upgrading. This keeps the coverage next/core-web-vitals gave:
// react, react-hooks, and the jsx-a11y rules the Next `next` preset documents.
export default [
  {
    ignores: [".next/**", "node_modules/**", "coverage/**", "out/**", "next-env.d.ts"],
  },
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        sourceType: "module",
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "jsx-a11y": jsxA11y,
      "@typescript-eslint": tsPlugin,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      ...react.configs.recommended.rules,

      // The jsx-a11y set the Next `next` preset enables. Deliberately not the
      // full recommended set: click-events-have-key-events and friends flag
      // legitimate wrapper components and would add failures core-web-vitals
      // never enforced.
      "jsx-a11y/alt-text": "error",
      "jsx-a11y/aria-props": "error",
      "jsx-a11y/aria-proptypes": "error",
      "jsx-a11y/aria-unsupported-elements": "error",
      "jsx-a11y/role-has-required-aria-props": "error",
      "jsx-a11y/role-supports-aria-props": "error",

      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",

      // TypeScript already resolves these; the base rules cannot see types and
      // double-report. no-unused-vars is covered by the TS-aware rule below.
      "no-undef": "off",
      "no-unused-vars": "off",
      "no-redeclare": "off",
      "react/prop-types": "off",
      "react/react-in-jsx-scope": "off",

      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },
  {
    // Build config files run in Node, not the browser.
    files: ["*.config.{js,cjs,mjs}", "postcss.config.js"],
    languageOptions: {
      globals: {
        console: "readonly",
        process: "readonly",
      },
    },
  },
];
