"""What other modules may do with papers. They use this, never `LibraryRepository` directly."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from tez.core.db import utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.library import citekeys
from tez.modules.library.models import (
    Collection,
    IdentifierScheme,
    Paper,
    PaperAuthor,
    PaperIdentifier,
    RelationKind,
    RetractionStatus,
)
from tez.modules.library.repository import AuthorInput, LibraryRepository

# The system collection new files land in until the user files them (plan, "Gelen kutusu").
INBOX = "inbox"
_FILLABLE = (
    "abstract",
    "year",
    "venue",
    "venue_type",
    "thesis_type",
    "volume",
    "issue",
    "pages",
    "language",
)
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

    def cards_where(self, *conditions: Any) -> list[PaperCard]:
        """Papers matching SQL conditions on `Paper`, for lists that filter in the database."""
        return self._cards(*conditions)

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

    def existing_ids(self, paper_ids: Iterable[str]) -> set[str]:
        return set(self._session.scalars(select(Paper.id).where(Paper.id.in_(set(paper_ids)))))

    def keep(self, paper_ids: Iterable[str]) -> tuple[int, int]:
        """Put papers in the library; returns (added, already there). The first date stays."""
        wanted = set(paper_ids)
        papers = list(self._session.scalars(select(Paper).where(Paper.id.in_(wanted))))
        if missing := wanted - {paper.id for paper in papers}:
            raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": sorted(missing)}, status=404)
        new = [paper for paper in papers if paper.library_added_at is None]
        now = utcnow()
        for paper in new:
            paper.library_added_at = now
        self.assign_citekeys(new)
        self._session.flush()
        return len(new), len(papers) - len(new)

    def assign_citekeys(self, papers: Iterable[Paper]) -> None:
        """Give each paper without a citation key one (`yilmaz2024automated`)."""
        reserved: set[str] = set()
        for paper in papers:
            if paper.citekey:
                continue
            first = paper.authors[0].author if paper.authors else None
            family = (first.family or first.display_name) if first else None
            key = citekeys.unique_key(
                self._session, citekeys.base_key(family, paper.year, paper.title), reserved
            )
            paper.citekey = key
            reserved.add(key)

    def backfill_citekeys(self) -> int:
        """Kept papers from before keys were made (Task 19) get one now."""
        missing = list(
            self._session.scalars(
                select(Paper).where(Paper.library_added_at.is_not(None), Paper.citekey.is_(None))
            )
        )
        self.assign_citekeys(missing)
        self._session.flush()
        return len(missing)

    def link_versions(self, preprint_id: str, published_id: str) -> None:
        self._repository.add_relation(preprint_id, published_id, RelationKind.VERSION_OF)

    def inbox_id(self) -> str:
        """The inbox collection, made the first time a file needs it."""
        found = self._session.scalar(
            select(Collection.id).where(Collection.is_system, Collection.name == INBOX)
        )
        if found is not None:
            return found
        return self._repository.add_collection(INBOX, is_system=True, sort_order=-1).id

    def put_in_inbox(self, paper_id: str) -> None:
        self._repository.add_to_collection(self.inbox_id(), paper_id)
