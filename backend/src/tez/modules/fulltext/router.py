from typing import Annotated

from fastapi import APIRouter, Depends, Query

from tez.modules.fulltext import service
from tez.modules.fulltext.schemas import FindResults, FulltextQuery, FulltextResults
from tez.modules.library.router import get_library
from tez.modules.library.service import Library

router = APIRouter(tags=["fulltext"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.post("/fulltext/search")
def search_fulltext(body: FulltextQuery, library: LibraryDep) -> FulltextResults:
    """Search inside the PDFs of library papers, page by page.

    Every word must be on the page, as a word or its beginning; "quoted words" must follow each
    other exactly. Turkish letters fold ("isik" = "Işık"). POST, because the list of papers to
    look in does not fit in an address.
    """
    return service.search(library.db, body)


@router.get("/attachments/{attachment_id}/find")
def find_in_document(
    attachment_id: str,
    library: LibraryDep,
    q: Annotated[str, Query(min_length=1, max_length=200)],
) -> FindResults:
    """Where a text is in one PDF: the pages with it, and how often. Case, accents, line breaks
    and hyphens at line ends do not matter."""
    return service.find(library.db, attachment_id, q)
