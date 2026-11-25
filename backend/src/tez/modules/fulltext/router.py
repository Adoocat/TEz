from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.fulltext import service
from tez.modules.fulltext.schemas import FulltextQuery, FulltextResults
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
