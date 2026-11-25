from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.notes import service
from tez.modules.notes.schemas import (
    Backlink,
    LinkSuggestion,
    NoteAppend,
    NoteCreate,
    NoteHit,
    NotePatch,
    NoteSummary,
    NoteView,
)

router = APIRouter(tags=["notes"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("/notes")
def list_notes(library: LibraryDep) -> list[NoteSummary]:
    return service.list_notes(library.db)


@router.post("/notes", status_code=201)
def create_note(body: NoteCreate, library: LibraryDep) -> NoteView:
    return service.create(library.db, body)


@router.get("/notes/search")
def search_notes(
    q: Annotated[str, Query(min_length=1, max_length=500)], library: LibraryDep
) -> list[NoteHit]:
    """Notes with every word of the query, best first."""
    return service.search(library.db, q)


@router.get("/notes/suggest")
def suggest_links(
    library: LibraryDep, q: Annotated[str, Query(max_length=200)] = ""
) -> list[LinkSuggestion]:
    """Notes and papers a link can point at, for `[[`."""
    return service.suggest(library.db, q)


@router.get("/notes/{note_id}")
def get_note(note_id: str, library: LibraryDep) -> NoteView:
    return service.get(library.db, note_id)


@router.patch("/notes/{note_id}")
def update_note(note_id: str, body: NotePatch, library: LibraryDep) -> NoteView:
    """Save changes. With `base_version`, a save based on an older text is `note.conflict`."""
    return service.update(library.db, note_id, body)


@router.post("/notes/{note_id}/append")
def append_to_note(note_id: str, body: NoteAppend, library: LibraryDep) -> NoteView:
    return service.append(library.db, note_id, body.text)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: str, library: LibraryDep) -> Response:
    """To the trash; `restore` brings it back."""
    service.delete(library.db, note_id)
    return Response(status_code=204)


@router.post("/notes/{note_id}/restore")
def restore_note(note_id: str, library: LibraryDep) -> NoteView:
    return service.restore(library.db, note_id)


@router.get("/notes/{note_id}/backlinks")
def note_backlinks(note_id: str, library: LibraryDep) -> list[Backlink]:
    return service.backlinks(library.db, note_id)


@router.get("/papers/{paper_id}/notes")
def paper_notes(paper_id: str, library: LibraryDep) -> list[Backlink]:
    """Notes attached to a paper, or linking to it or to a place in its PDFs."""
    return service.of_paper(library.db, paper_id)
