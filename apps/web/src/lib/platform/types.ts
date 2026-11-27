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

/**
 * Something TEz was asked to open from outside: `tez <file>`, "Open with TEz", a `tez://`
 * link (Task 22). The desktop shell resolves paths; see apps/desktop/src-tauri/src/open.rs.
 */
export type OpenRequest =
  | { kind: "focus" }
  | { kind: "pdf"; path: string }
  | { kind: "import"; path: string }
  | { kind: "folder"; path: string; is_library: boolean; pdfs: string[]; truncated: boolean }
  | { kind: "link"; url: string }
  | { kind: "missing"; path: string }
  | { kind: "unsupported"; path: string };

/** Everything that differs between the desktop app (Tauri) and a plain browser. */
export interface Platform {
  kind: "tauri" | "browser";
  /** Report the backend's state now and on every change; returns an unsubscribe function. */
  connectBackend(onChange: (state: BackendState) => void): () => void;
  /**
   * Hand over open requests: those waiting since start-up at once, later ones as they come.
   * A browser has none. Returns an unsubscribe function.
   */
  onOpenRequests(handle: (requests: OpenRequest[]) => void): () => void;
  /**
   * Open an http(s) link (DOI, arXiv, an open-access PDF) in the user's own browser. The
   * desktop window ignores `target="_blank"`, so outside links go through here.
   */
  openExternal(url: string): Promise<void>;
  /** Put text on the clipboard; with `html` also as rich text, which pastes into Word formatted. */
  copyText(text: string, html?: string): Promise<void>;
  /**
   * Save a file the app made (a bibliography, a table) where the user's downloads go. Text is
   * saved as UTF-8; bytes (an Excel file) as they are.
   */
  saveFile(fileName: string, content: string | Uint8Array, mimeType: string): Promise<void>;
}
