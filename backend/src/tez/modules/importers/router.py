from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.importers import presets, service
from tez.modules.importers.schemas import (
    ImportOutcome,
    ImportPreview,
    ImportPreviewRequest,
    ImportRequest,
    PresetView,
)
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/imports", tags=["imports"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("/presets")
def list_presets() -> list[PresetView]:
    """The database presets on offer: only those verified with a real export (Task 26)."""
    return [
        PresetView(key=p.key, name=p.name, formats=list(p.formats)) for p in presets.available()
    ]


@router.post("/preview")
def preview_import(body: ImportPreviewRequest, library: LibraryDep) -> ImportPreview:
    """Read a BibTeX or RIS file and say what importing it would do. Writes nothing.

    With `saved_search_id`, it also says how many records are new since the last import.
    """
    data = service.read_input(body)
    return service.preview(library.db, body.file_name, data, body.saved_search_id)


@router.post("", status_code=201)
def import_file(body: ImportRequest, library: LibraryDep) -> ImportOutcome:
    """Import a BibTeX or RIS file. With `log`, it becomes a search run in the review."""
    return service.run_import(library.db, library.path, body, initiated_via=body.initiated_via)
