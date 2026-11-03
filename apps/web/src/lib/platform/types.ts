export interface BackendConnection {
  /** Absolute API origin, or "/api" behind the Vite dev proxy. */
  baseUrl: string;
  token: string;
}

export interface BackendError {
  code: string;
  params?: Record<string, unknown>;
}

export type BackendState =
  | { status: "starting" }
  | { status: "ready"; connection: BackendConnection }
  | { status: "failed"; error: BackendError };

/** Everything that differs between the desktop app (Tauri) and a plain browser. */
export interface Platform {
  kind: "tauri" | "browser";
  /** Report the backend's state now and on every change; returns an unsubscribe function. */
  connectBackend(onChange: (state: BackendState) => void): () => void;
}
