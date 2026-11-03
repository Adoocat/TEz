"""SQL access for papers, authors, collections and tags. No business rules beyond integrity."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tez.core.db import utcnow
from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import (
    Author,
    Collection,
    CollectionPaper,
    IdentifierScheme,
    Paper,
    PaperAuthor,
    PaperIdentifier,
    PaperRelation,
    PaperTag,
    RelationKind,
    SmartCollection,
    Tag,
    VenueType,
)
from tez.shared.text import fold, normalize_title


@dataclass(frozen=True)
class AuthorInput:
    display_name: str
    family: str | None = None
    given: str | None = None
    orcid: str | None = None
    affiliation_raw: str | None = None


class LibraryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- papers -----------------------------------------------------------------------

    def add_paper(
        self,
        title: str,
        *,
        identifiers: Sequence[tuple[IdentifierScheme, str]] = (),
        authors: Sequence[AuthorInput] = (),
        abstract: str | None = None,
        year: int | None = None,
        venue: str | None = None,
        venue_type: VenueType | None = None,
        url: str | None = None,
        oa_url: str | None = None,
        language: str | None = None,
        citekey: str | None = None,
        citation_count: int | None = None,
    ) -> Paper:
        paper = Paper(
            title=title,
            title_norm=normalize_title(title),
            abstract=abstract,
            year=year,
            venue=venue,
            venue_type=venue_type,
            url=url,
            oa_url=oa_url,
            language=language,
            citekey=citekey,
            citation_count=citation_count,
        )
        paper.identifiers = [PaperIdentifier(scheme=s, value=v) for s, v in identifiers]
        paper.authors = [
            PaperAuthor(author=self._author_for(a), position=i, affiliation_raw=a.affiliation_raw)
            for i, a in enumerate(authors)
        ]
        self.session.add(paper)
        self.session.flush()
        return paper

    def _author_for(self, given: AuthorInput) -> Author:
        """The same person is one row only when an ORCID says so; names are ambiguous."""
        if given.orcid is not None:
            existing = self.session.scalar(select(Author).where(Author.orcid == given.orcid))
            if existing is not None:
                return existing
        author = Author(
            display_name=given.display_name,
            family=given.family,
            given=given.given,
            orcid=given.orcid,
        )
        self.session.add(author)
        self.session.flush()
        return author

    def get_paper(self, paper_id: str, *, include_deleted: bool = False) -> Paper | None:
        paper = self.session.get(Paper, paper_id)
        if paper is None or (paper.deleted_at is not None and not include_deleted):
            return None
        return paper

    def find_by_identifier(self, scheme: IdentifierScheme, value: str) -> Paper | None:
        return self.session.scalar(
            select(Paper)
            .join(PaperIdentifier)
            .where(PaperIdentifier.scheme == scheme, PaperIdentifier.value == value)
        )

    def list_papers(self, *, include_deleted: bool = False) -> list[Paper]:
        query = select(Paper).order_by(Paper.created_at, Paper.id)
        if not include_deleted:
            query = query.where(Paper.deleted_at.is_(None))
        return list(self.session.scalars(query))

    def soft_delete(self, paper_id: str) -> None:
        self._paper(paper_id).deleted_at = utcnow()
        self.session.flush()

    def restore(self, paper_id: str) -> None:
        self._paper(paper_id).deleted_at = None
        self.session.flush()

    def add_relation(
        self, from_paper_id: str, to_paper_id: str, kind: RelationKind
    ) -> PaperRelation:
        relation = PaperRelation(from_paper_id=from_paper_id, to_paper_id=to_paper_id, kind=kind)
        self.session.add(relation)
        self.session.flush()
        return relation

    def _paper(self, paper_id: str) -> Paper:
        paper = self.session.get(Paper, paper_id)
        if paper is None:
            raise LookupError(f"paper {paper_id} not found")
        return paper

    # --- collections ------------------------------------------------------------------

    def add_collection(
        self,
        name: str,
        *,
        parent_id: str | None = None,
        sort_order: int = 0,
        is_system: bool = False,
    ) -> Collection:
        collection = Collection(
            name=name, parent_id=parent_id, sort_order=sort_order, is_system=is_system
        )
        self.session.add(collection)
        self.session.flush()
        return collection

    def child_collections(self, parent_id: str | None) -> list[Collection]:
        query = select(Collection).order_by(Collection.sort_order, Collection.created_at)
        query = query.where(
            Collection.parent_id.is_(None)
            if parent_id is None
            else Collection.parent_id == parent_id
        )
        return list(self.session.scalars(query))

    def move_collection(self, collection_id: str, new_parent_id: str | None) -> None:
        """Re-parent a collection; refuses to move it under itself or its descendants."""
        ancestor = new_parent_id
        while ancestor is not None:
            if ancestor == collection_id:
                raise TezError(ErrorCode.COLLECTION_CYCLE, {"collection_id": collection_id})
            ancestor = self.session.scalar(
                select(Collection.parent_id).where(Collection.id == ancestor)
            )
        collection = self.session.get(Collection, collection_id)
        if collection is None:
            raise LookupError(f"collection {collection_id} not found")
        collection.parent_id = new_parent_id
        self.session.flush()

    def add_to_collection(self, collection_id: str, paper_id: str) -> None:
        exists = self.session.scalar(
            select(CollectionPaper.id).where(
                CollectionPaper.collection_id == collection_id,
                CollectionPaper.paper_id == paper_id,
            )
        )
        if exists is None:
            self.session.add(CollectionPaper(collection_id=collection_id, paper_id=paper_id))
            self.session.flush()

    def remove_from_collection(self, collection_id: str, paper_id: str) -> None:
        self.session.execute(
            delete(CollectionPaper).where(
                CollectionPaper.collection_id == collection_id,
                CollectionPaper.paper_id == paper_id,
            )
        )

    def papers_in_collection(self, collection_id: str) -> list[Paper]:
        return list(
            self.session.scalars(
                select(Paper)
                .join(CollectionPaper)
                .where(CollectionPaper.collection_id == collection_id)
                .order_by(CollectionPaper.created_at)
            )
        )

    # --- tags -------------------------------------------------------------------------

    def add_tag(self, name: str, *, color: str | None = None) -> Tag:
        tag = Tag(name=name, color=color)
        self.session.add(tag)
        self.session.flush()
        return tag

    def tag_paper(self, paper_id: str, tag_id: str) -> None:
        exists = self.session.scalar(
            select(PaperTag.id).where(PaperTag.paper_id == paper_id, PaperTag.tag_id == tag_id)
        )
        if exists is None:
            self.session.add(PaperTag(paper_id=paper_id, tag_id=tag_id))
            self.session.flush()

    def untag_paper(self, paper_id: str, tag_id: str) -> None:
        self.session.execute(
            delete(PaperTag).where(PaperTag.paper_id == paper_id, PaperTag.tag_id == tag_id)
        )

    def tags_of(self, paper_id: str) -> list[Tag]:
        """Alphabetical the way a reader expects ("önemli" before "yöntem"), not by code point."""
        tags = self.session.scalars(select(Tag).join(PaperTag).where(PaperTag.paper_id == paper_id))
        return sorted(tags, key=lambda tag: fold(tag.name))

    # --- smart collections ------------------------------------------------------------

    def add_smart_collection(self, name: str, filter_json: dict[str, Any]) -> SmartCollection:
        smart = SmartCollection(name=name, filter_json=filter_json)
        self.session.add(smart)
        self.session.flush()
        return smart
