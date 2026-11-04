"""What other modules may do with papers. They use this, never `LibraryRepository` directly."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tez.modules.library.models import (
    IdentifierScheme,
    Paper,
    PaperAuthor,
    PaperIdentifier,
    RelationKind,
    RetractionStatus,
)
from tez.modules.library.repository import AuthorInput, LibraryRepository

_FILLABLE = ("abstract", "year", "venue", "venue_type", "volume", "issue", "pages", "language")
_FILLABLE_LINKS = ("url", "oa_url")


@dataclass(frozen=True)
class FirstAuthor:
    display_name: str
    family: str | None


@dataclass(frozen=True)
class PaperCard:
    """A paper as lists show it."""

    paper: Paper
    identifiers: Mapping[IdentifierScheme, str]
    first_author: FirstAuthor | None
    author_count: int


def _card(paper: Paper) -> PaperCard:
    first = paper.authors[0].author if paper.authors else None
    return PaperCard(
        paper=paper,
        identifiers={i.scheme: i.value for i in paper.identifiers},
        first_author=FirstAuthor(first.display_name, first.family) if first else None,
        author_count=len(paper.authors),
    )


class PaperService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repository = LibraryRepository(session)

    def _cards(self, *conditions: Any) -> list[PaperCard]:
        query = (
            select(Paper)
            .where(*conditions)
            .options(
                selectinload(Paper.identifiers),
                selectinload(Paper.authors).selectinload(PaperAuthor.author),
            )
        )
        return [_card(paper) for paper in self._session.scalars(query)]

    def all_cards(self) -> list[PaperCard]:
        """Every paper, including the trash: a trashed paper's DOI still belongs to it."""
        return self._cards()

    def cards(self, paper_ids: Iterable[str]) -> dict[str, PaperCard]:
        cards = self._cards(Paper.id.in_(list(paper_ids)))
        return {card.paper.id: card for card in cards}

    def add(
        self,
        title: str,
        *,
        identifiers: Mapping[IdentifierScheme, str],
        authors: Iterable[AuthorInput],
        is_retracted: bool = False,
        **fields: Any,
    ) -> Paper:
        paper = self._repository.add_paper(
            title, identifiers=list(identifiers.items()), authors=list(authors), **fields
        )
        if is_retracted:
            paper.retraction_status = RetractionStatus.RETRACTED
        return paper

    def fill_missing(
        self,
        paper_id: str,
        *,
        identifiers: Mapping[IdentifierScheme, str],
        is_retracted: bool = False,
        **fields: Any,
    ) -> None:
        """Add what another source knows and this paper lacks. Existing values stay."""
        paper = self._session.get(Paper, paper_id)
        if paper is None:
            raise LookupError(f"paper {paper_id} not found")
        for name in (*_FILLABLE, *_FILLABLE_LINKS, "citation_count"):
            value = fields.get(name)
            if value is not None and getattr(paper, name) is None:
                setattr(paper, name, value)
        if is_retracted:
            paper.retraction_status = RetractionStatus.RETRACTED
        known = {i.scheme for i in paper.identifiers}
        for scheme, value in identifiers.items():
            if scheme not in known:
                paper.identifiers.append(PaperIdentifier(scheme=scheme, value=value))
        self._session.flush()

    def link_versions(self, preprint_id: str, published_id: str) -> None:
        self._repository.add_relation(preprint_id, published_id, RelationKind.VERSION_OF)
