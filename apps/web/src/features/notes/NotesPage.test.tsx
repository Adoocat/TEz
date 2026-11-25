// CodeMirror needs a layout jsdom does not have: a text area stands in for the editor here. The
// real one is checked by e2e/notes.spec.ts.
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import {
  anchorView,
  fakeBackend,
  noteView,
  readyPlatform,
  type FakeBackend,
} from "@/test/fakeBackend";

import type { EditorProps } from "./MarkdownEditor";
import { useNoteMode } from "./store";

vi.mock("./MarkdownEditor", () => ({
  MarkdownEditor: ({ initial, label, onChange }: EditorProps) => (
    <textarea
      aria-label={label}
      defaultValue={initial}
      onChange={(event) => {
        onChange(event.target.value);
      }}
    />
  ),
}));

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true, focus: false });
  useNoteMode.setState({ mode: "both" });
});

function open(hash: string, prepare?: (backend: FakeBackend) => void, backend?: FakeBackend) {
  window.location.hash = hash;
  const used = backend ?? fakeBackend({ language: "en" });
  if (!backend) {
    used.notes = [
      noteView({ id: "a", title: "Method", body: "Old text" }),
      noteView({ id: "b", title: "Sampling", parent_id: "a" }),
    ];
  }
  prepare?.(used);
  const user = userEvent.setup();
  let closed = false;
  const fetch = (request: Request) =>
    closed ? new Promise<Response>(() => undefined) : used.fetch(request);
  render(<App platform={readyPlatform} fetch={fetch} />);
  return {
    backend: used,
    user,
    /** The window is gone: nothing it still asks for happens. */
    close: () => {
      closed = true;
    },
  };
}

const bodyField = () => screen.findByRole("textbox", { name: "Note text" });
const saves = (backend: FakeBackend) =>
  backend.requests.filter((r) => r.method === "PATCH").map((r) => r.body);

describe("the notes screen", () => {
  it("shows the tree and opens a new note inside another", async () => {
    const { backend, user } = open("#/notes");
    const tree = await screen.findByRole("list", { name: "Note tree" });
    expect((await within(tree).findAllByRole("link")).map((l) => l.textContent)).toEqual([
      "Method",
      "Sampling",
    ]);

    await user.click(screen.getByRole("button", { name: "New note inside Method" }));

    expect(await screen.findByRole("textbox", { name: "Note title" })).toHaveValue("Untitled note");
    expect(backend.notes.at(-1)?.parent_id).toBe("a");
  });

  it("saves by itself, based on the version it has", async () => {
    const { backend, user } = open("#/notes/a");

    await user.type(await bodyField(), " and new");
    expect(screen.getByText("Not saved yet")).toBeInTheDocument();
    expect(await screen.findByText("Saved")).toBeInTheDocument();
    await user.type(await bodyField(), "!");
    await waitFor(() => {
      expect(saves(backend)).toEqual([
        { title: "Method", body: "Old text and new", base_version: 1 },
        { title: "Method", body: "Old text and new!", base_version: 2 },
      ]);
    });
  });

  it("keeps the text when the window closes before it was saved", async () => {
    const first = open("#/notes/a", (backend) => {
      // The connection is gone; every save fails.
      backend.noteFailures = Array.from({ length: 9 }, () => ({ status: 500, code: "internal" }));
    });
    await first.user.type(await bodyField(), " precious");
    expect(
      await screen.findByText(/Could not be saved. Your text is kept on this device./),
    ).toBeInTheDocument();
    first.close();
    cleanup();
    first.backend.noteFailures = [];

    open("#/notes/a", undefined, first.backend);

    expect(await bodyField()).toHaveValue("Old text precious");
    await waitFor(() => {
      expect(first.backend.notes[0]?.body).toBe("Old text precious");
    });
    expect(localStorage.getItem("tez.note.draft.a")).toBeNull();
  });

  it("saves at once when the note is left", async () => {
    const { backend, user } = open("#/notes/a");
    await user.type(await bodyField(), "?");
    await user.click(screen.getByRole("link", { name: "Sampling" }));

    await waitFor(() => {
      expect(backend.notes[0]?.body).toBe("Old text?");
    });
  });

  it("asks when the note was changed somewhere else", async () => {
    const { backend, user } = open("#/notes/a");
    const field = await bodyField();
    const [note] = backend.notes;
    if (!note) throw new Error("no note");
    Object.assign(note, { body: "Theirs", version: 7 });

    await user.type(field, " mine");
    expect(await screen.findByText(/changed somewhere else/)).toBeInTheDocument();
    expect(note.body).toBe("Theirs");

    await user.click(screen.getByRole("button", { name: "Keep my text" }));
    await waitFor(() => {
      expect(note.body).toBe("Old text mine");
    });
    expect(await screen.findByText("Saved")).toBeInTheDocument();
  });

  it("shows the saved note instead, if that is wanted", async () => {
    const { backend, user } = open("#/notes/a", () => {
      localStorage.setItem(
        "tez.note.draft.a",
        JSON.stringify({ title: "Method", body: "from an old window", version: 0 }),
      );
    });
    expect(await screen.findByText(/unsaved text from an earlier window/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Use the saved note" }));

    await waitFor(() => {
      expect(screen.queryByText(/unsaved text/)).not.toBeInTheDocument();
    });
    expect(await bodyField()).toHaveValue("Old text");
    expect(saves(backend)).toEqual([]);
  });

  it("moves a note in the tree and saves on from there", async () => {
    const { backend, user } = open("#/notes/b");
    await bodyField();
    await screen.findByRole("option", { name: "Method" });

    await user.selectOptions(screen.getByRole("combobox", { name: "Place in the tree" }), "");
    await waitFor(() => {
      expect(backend.notes[1]?.parent_id).toBeNull();
    });
    await user.type(await bodyField(), "x");
    await waitFor(() => {
      expect(backend.notes[1]?.body).toBe("x");
    });
  });

  it("deletes a note and brings it back", async () => {
    const { backend, user } = open("#/notes/a");
    await bodyField();

    await user.click(screen.getByRole("button", { name: "Delete the note" }));
    expect(await screen.findByText("This note was deleted.")).toBeInTheDocument();
    expect(backend.notes.map((n) => n.id)).toEqual(["b"]);

    await user.click(screen.getByRole("button", { name: "Restore the note" }));
    expect(await bodyField()).toBeInTheDocument();
  });

  it("searches notes", async () => {
    const { user } = open("#/notes");
    await user.type(await screen.findByRole("searchbox", { name: "Search notes" }), "Old");

    const results = await screen.findByRole("list", { name: "Notes found" });
    expect(await within(results).findByRole("link", { name: /Method/ })).toHaveAttribute(
      "href",
      "#/notes/a",
    );
  });
});

describe("a note as it reads", () => {
  it("shows links as chips, marks broken ones, and runs nothing", async () => {
    open("#/notes/a", (backend) => {
      const [note] = backend.notes;
      if (!note) return;
      note.body = [
        "# Heading",
        "[Kim 2024](tez:paper/p1) [[Nowhere]] [site](https://example.org)",
        "<script>alert(1)</script> [bad](javascript:alert(1)) ![pic](https://example.org/x.png)",
      ].join("\n\n");
      note.links = [
        {
          target_type: "paper",
          target_id: "p1",
          label: "Kim 2024",
          status: "ok",
          title: "A paper",
          anchor: null,
        },
        {
          target_type: null,
          target_id: null,
          label: "Nowhere",
          status: "broken",
          title: null,
          anchor: null,
        },
      ];
    });

    const preview = await screen.findByRole("article", { name: "Preview" });
    expect(await within(preview).findByRole("heading", { name: "Heading" })).toBeInTheDocument();
    expect(within(preview).getByRole("link", { name: "Kim 2024" })).not.toHaveClass(
      "note-chip-broken",
    );
    expect(within(preview).getByRole("link", { name: "Nowhere" })).toHaveClass("note-chip-broken");
    expect(preview.querySelector("script, img")).toBeNull();
    expect(within(preview).queryByRole("link", { name: "bad" })).not.toBeInTheDocument();
  });

  it("opens the reader at the place a chip names, and lists what is cited", async () => {
    const anchor = anchorView({ id: "a7", attachment_id: "att-9", page: 7 });
    const { user } = open("#/notes/a", (backend) => {
      const [note] = backend.notes;
      if (!note) return;
      note.body = "[Lovelace 2024, p. 7](tez:anchor/a7)";
      note.links = [
        {
          target_type: "anchor",
          target_id: "a7",
          label: "Lovelace 2024, p. 7",
          status: "ok",
          title: "First paper",
          anchor,
        },
      ];
      backend.backlinks.a = [{ note_id: "b", title: "Sampling", passage: "see Method" }];
      backend.anchors.a7 = anchor;
    });

    const inspector = await screen.findByRole("complementary", { name: "Inspector" });
    expect(await within(inspector).findByText("Links to this note (1)")).toBeInTheDocument();
    expect(within(inspector).getByText("see Method")).toBeInTheDocument();
    expect(within(inspector).getByText("Cited here (1)")).toBeInTheDocument();
    expect(
      within(inspector).getByRole("button", { name: "Lovelace et al. 2024 · p. 7" }),
    ).toBeInTheDocument();

    await user.click(await screen.findByRole("link", { name: "Lovelace 2024, p. 7" }));
    await waitFor(() => {
      expect(window.location.hash).toContain("#/reader/att-9");
    });
  });
});
