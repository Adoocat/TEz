from typing import Annotated

from fastapi import APIRouter, Depends

from tez.modules.library.router import get_library
from tez.modules.library.service import Library
from tez.modules.prisma import service
from tez.modules.prisma.schemas import PrismaCounts, PrismaLabels
from tez.modules.reviews import service as reviews_service

router = APIRouter(prefix="/reviews/{review_id}/prisma", tags=["prisma"])

LibraryDep = Annotated[Library, Depends(get_library)]


@router.get("")
def get_counts(review_id: str, library: LibraryDep) -> PrismaCounts:
    """Every box of the PRISMA 2020 flow diagram, derived now from the review's records."""
    return service.counts(library.db, review_id)


@router.get("/labels")
def get_labels(review_id: str, library: LibraryDep) -> PrismaLabels:
    return PrismaLabels.model_validate(
        {"labels": reviews_service.prisma_labels(library.db, review_id)}
    )


@router.put("/labels")
def put_labels(review_id: str, body: PrismaLabels, library: LibraryDep) -> PrismaLabels:
    """Keep the edited box titles. Only words are stored; the numbers stay derived."""
    labels: dict[str, str] = {str(key): text for key, text in body.labels.items()}
    saved = reviews_service.set_prisma_labels(library.db, review_id, labels)
    return PrismaLabels.model_validate({"labels": saved})
