import { readFileSync } from "node:fs";
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import pkg from "./package.json" with { type: "json" };

// `pnpm dev` runs the backend with the development library (backend/.dev/TEz Library).
// The browser calls /api; this proxy forwards to the backend and adds the token from the
// library's discovery file, so the token never reaches the page.
const devInstance = path.resolve(
  import.meta.dirname,
  "../../backend/.dev/TEz Library/.tez/instance.json",
);

function devToken(): string | null {
  try {
    const instance = JSON.parse(readFileSync(devInstance, "utf8")) as {
      api?: { token?: string };
    };
    return instance.api?.token ?? null;
  } catch {
    return null; // backend not started yet
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  // Fixed port: Tauri's devUrl points here (apps/desktop/src-tauri/tauri.conf.json).
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        rewrite: (url) => url.replace(/^\/api/, ""),
        configure(proxy) {
          proxy.on("proxyReq", (request) => {
            const token = devToken();
            if (token) request.setHeader("Authorization", `Bearer ${token}`);
          });
        },
      },
    },
  },
  clearScreen: false,
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
