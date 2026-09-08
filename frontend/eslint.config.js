// Flat config (ESLint 9). Two environments: Electron main (Node/CommonJS) and the
// renderer + tests (browser / ES modules).
"use strict";

const js = require("@eslint/js");

module.exports = [
  js.configs.recommended,
  {
    ignores: ["node_modules/**", "../installer/output/**", "playwright-report/**", "test-results/**"],
  },
  {
    files: ["src/main/**/*.js", "build/**/*.js", "eslint.config.js"],
    languageOptions: {
      sourceType: "commonjs",
      globals: {
        require: "readonly", module: "writable", exports: "writable", process: "readonly",
        __dirname: "readonly", console: "readonly", setTimeout: "readonly", clearTimeout: "readonly",
      },
    },
  },
  {
    files: ["src/renderer/**/*.js"],
    languageOptions: {
      sourceType: "module",
      globals: {
        window: "readonly", document: "readonly", fetch: "readonly", console: "readonly",
        localStorage: "readonly", setTimeout: "readonly", clearTimeout: "readonly",
        URLSearchParams: "readonly", URL: "readonly", FormData: "readonly",
      },
    },
  },
  {
    files: ["tests/**/*.js", "playwright.config.js"],
    languageOptions: {
      sourceType: "commonjs",
      globals: {
        require: "readonly", module: "writable", process: "readonly", __dirname: "readonly",
        console: "readonly", setTimeout: "readonly", URL: "readonly", Buffer: "readonly",
        // referenced inside page.evaluate() callbacks (executed in the browser)
        window: "readonly", document: "readonly", getComputedStyle: "readonly",
      },
    },
  },
];
