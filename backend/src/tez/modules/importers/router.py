from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.importers import service
from tez.modules.importers.schemas import ImportFile, ImportOutcome, ImportPreview, ImportRequest
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(prefix="/imports", tags=["imports"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("/preview")
def preview_import(body: ImportFile, library: LibraryDep) -> ImportPreview:
    """Read a BibTeX or RIS file and say what importing it would do. Writes nothing."""
    return service.preview(library.db, body.file_name, service.read_input(body))


@router.post("", status_code=201)
def import_file(body: ImportRequest, library: LibraryDep) -> ImportOutcome:
    """Import a BibTeX or RIS file. With `log`, it becomes a search run in the review."""
    return service.run_import(library.db, library.path, body)
