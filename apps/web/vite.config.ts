import { createReadStream, existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
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

// pdf.js loads these by address, so they are copied as they are (src/lib/pdf.ts).
const pdfjsFolders = ["cmaps", "iccs", "standard_fonts", "wasm"];
/** What is left out of them: the Liberation fonts are GPL-2.0 (CLAUDE.md rule 6; pdf.js uses the
 * system's Arial or Helvetica instead), and the .js files are fallbacks for browsers without
 * WebAssembly. */
const pdfjsLeftOut = /^(Liberation|LICENSE_LIBERATION|quickjs|LICENSE_.*QUICKJS)|\.js$/;
const pdfjsRoot = path.resolve(import.meta.dirname, "node_modules/pdfjs-dist");

function pdfjsAssets(): Plugin {
  return {
    name: "tez-pdfjs-assets",
    configureServer(server) {
      server.middlewares.use("/pdfjs", (request, response, next) => {
        const [folder = "", name = ""] = new URL(request.url ?? "/", "http://localhost").pathname
          .slice(1)
          .split("/");
        const file = path.join(pdfjsRoot, folder, path.basename(name));
        if (
          !name ||
          pdfjsLeftOut.test(name) ||
          !pdfjsFolders.includes(folder) ||
          !existsSync(file)
        ) {
          next();
          return;
        }
        response.setHeader(
          "Content-Type",
          name.endsWith(".wasm") ? "application/wasm" : "application/octet-stream",
        );
        createReadStream(file).pipe(response);
      });
    },
    generateBundle() {
      for (const folder of pdfjsFolders) {
        for (const name of readdirSync(path.join(pdfjsRoot, folder))) {
          if (pdfjsLeftOut.test(name)) continue;
          this.emitFile({
            type: "asset",
            fileName: `pdfjs/${folder}/${name}`,
            source: readFileSync(path.join(pdfjsRoot, folder, name)),
          });
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), pdfjsAssets()],
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
    // e2e/ holds Playwright tests (pnpm e2e), which need a real browser and backend.
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // The UI tests click through whole screens; on a busy machine (`pnpm check` runs the
    // groups side by side) the default 5 s cut some of them off at random.
    testTimeout: 15_000,
  },
});
