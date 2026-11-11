// Browser mode. `tez serve` prints a link like Jupyter's, with the API address and the token
// in the URL fragment (never sent to a server, never in logs): `#api=http://...&token=...`.
// It is kept for the tab's lifetime and removed from the address bar. In development
// (`pnpm dev`) the Vite proxy at /api adds the token itself (vite.config.ts).
import type { BackendState, Platform } from "./types";

const SESSION_KEY = "tez.backend";

interface Stored {
  api: string;
  token: string;
}

export function takeConnectionFromUrl(location: Location, history: History): Stored | null {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  const api = params.get("api");
  const token = params.get("token");
  if (!api || !token) return null;
  // Drop the secret from the address bar (and from bookmarks or screenshots of it).
  history.replaceState(null, "", location.pathname + location.search);
  return { api, token };
}

function stored(): Stored | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as Stored) : null;
  } catch {
    return null;
  }
}

export function browserBackendState(dev: boolean): BackendState {
  const fromUrl = takeConnectionFromUrl(window.location, window.history);
  if (fromUrl) {
    try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(fromUrl));
    } catch {
      // Private mode without storage: works until the tab reloads.
    }
  }
  const connection = fromUrl ?? stored();
  if (connection) {
    return { status: "ready", connection: { baseUrl: connection.api, token: connection.token } };
  }
  if (dev) return { status: "ready", connection: { baseUrl: "/api", token: "" } };
  return { status: "failed", error: { code: "backend.no_token" } };
}

export const browserPlatform: Platform = {
  kind: "browser",
  connectBackend(onChange) {
    onChange(browserBackendState(import.meta.env.DEV));
    return () => undefined;
  },
  // Files and links reach the desktop app only.
  onOpenRequests: () => () => undefined,
  openExternal(url) {
    window.open(url, "_blank", "noopener,noreferrer");
    return Promise.resolve();
  },
};
