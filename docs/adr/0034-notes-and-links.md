# 0034 — Notes: links by id, names for typing, a tree and saved versions

- **Status:** Accepted
- **Date:** 2026-11-25
- **Tasks:** 48 (note service), 49 (notes screen), 50 (from the reader to a note)

## Context

The plan has `note` (title, Markdown body, paper, review) and `note_link`, filled from the Markdown at every save, with backlinks as the reverse query. Design 5.3 adds a tree of notes and `[[` for links, shown as chips. Acceptance: links follow the text at every save; a link whose target is gone is marked broken.

## Decision

- **Links are Markdown links with a `tez:` address:** `[Kim et al. 2024, p. 7](tez:anchor/<id>)`, `tez:paper/<id>`, `tez:note/<id>`. The body stays plain Markdown that other programs can show, and a link survives its target being renamed. The editor inserts these; nobody types them.
- **`[[name]]` works for typing by hand.** It is looked up when the note is saved (a note's title, then a citation key, then a paper's title, all folded) and when a note with that name appears. Renaming a note rewrites `[[old name]]` in the notes that link to it into a link by id.
- **`note_link.target_id` is not a foreign key**, and is null for a name that names nothing. Whether a link is `ok` or `broken` is worked out when a note is read: a trashed note or paper, a missing or lost anchor (ADR 0033) is broken, and becomes whole again when its target comes back.
- **Additions to the plan's table:** `parent_id` (the tree of design 5.3), `version` (every save counts up; a save based on an older one is `note.conflict`, so two windows do not overwrite each other) and `deleted_at` (a deleted note can be restored; notes inside it move up).
- **`note_fts`** holds the folded title and the folded body without link addresses. It is written with the note, in the same transaction.

## Consequences

- Links inside code blocks are text.
- A name that is both a note's title and a paper's means the note.
- `append` adds to a note without its editor open; it counts as a save, so an open editor with older text is told.
- No new backend dependency.

## The notes screen (Task 49)

- **CodeMirror 6** (MIT) edits the Markdown; links are drawn as chips, and raw while the cursor is in them. `[[` asks the backend for suggestions, in its order. The screen is loaded when it is first opened, so the editor is not part of the start-up bundle.
- **The preview is react-markdown** (MIT): it builds elements and never raw HTML, so a note cannot run code. Pictures are not loaded, because an address in a note must not reach the network (rule 1).
- **Nothing typed is lost.** Every change is first written to this device (`localStorage`), then saved 0.7 s later, or at once when the note is left or the window hidden. The local copy goes only when the save is confirmed. A copy found at the next opening is saved if it fits the note's version; otherwise the user chooses between the two texts.
- Not built: tags and folders of design 5.3 (the tree's notes do what folders would), and moving notes by dragging (a place selector does it).
