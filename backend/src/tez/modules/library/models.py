"""Library core: papers, identifiers, authors, collections, tags (plan, data model group 1)."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tez.core.db import Base, TimestampMixin, UtcDateTime, enum_type


class VenueType(StrEnum):
    JOURNAL = "journal"
    CONFERENCE = "conference"
    PREPRINT = "preprint"
    BOOK = "book"
    CHAPTER = "chapter"
    THESIS = "thesis"
    REPORT = "report"
    OTHER = "other"


class ThesisType(StrEnum):
    """The degree a thesis is for (Task 28); None when the source does not say."""

    MASTERS = "masters"
    DOCTORAL = "doctoral"


class ReadingStatus(StrEnum):
    UNREAD = "unread"
    READING = "reading"
    READ = "read"


class RetractionStatus(StrEnum):
    NONE = "none"
    RETRACTED = "retracted"
    EXPRESSION_OF_CONCERN = "expression_of_concern"


class IdentifierScheme(StrEnum):
    DOI = "doi"
    ARXIV = "arxiv"
    S2 = "s2"
    OPENALEX = "openalex"
    DBLP = "dblp"
    ISBN = "isbn"
    ZOTERO = "zotero"
    PMID = "pmid"
    PMCID = "pmcid"


class RelationKind(StrEnum):
    VERSION_OF = "version_of"
    ERRATUM_OF = "erratum_of"
    RETRACTION_OF = "retraction_of"


class Paper(TimestampMixin, Base):
    __tablename__ = "paper"
    __table_args__ = (CheckConstraint("citation_count >= 0", name="citation_count"),)

    title: Mapped[str] = mapped_column(Text)
    # Folded by tez.shared.text.normalize_title; the key for search and deduplication.
    title_norm: Mapped[str] = mapped_column(Text, index=True)
    abstract: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    venue: Mapped[str | None] = mapped_column(Text)
    venue_type: Mapped[VenueType | None] = mapped_column(enum_type(VenueType, "venue_type"))
    # Only for venue_type THESIS.
    thesis_type: Mapped[ThesisType | None] = mapped_column(enum_type(ThesisType, "thesis_type"))
    volume: Mapped[str | None] = mapped_column(String(32))
    issue: Mapped[str | None] = mapped_column(String(32))
    pages: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str | None] = mapped_column(String(16))
    url: Mapped[str | None] = mapped_column(Text)
    oa_url: Mapped[str | None] = mapped_column(Text)
    citation_count: Mapped[int | None] = mapped_column(Integer)
    reading_status: Mapped[ReadingStatus] = mapped_column(
        enum_type(ReadingStatus, "reading_status"), default=ReadingStatus.UNREAD
    )
    citekey: Mapped[str | None] = mapped_column(String(128), unique=True)
    retraction_status: Mapped[RetractionStatus] = mapped_column(
        enum_type(RetractionStatus, "retraction_status"), default=RetractionStatus.NONE
    )
    # Soft delete (trash); hard delete only when the trash is emptied.
    deleted_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    # Set when the user keeps the paper. Every search result has a row, so a row alone says
    # nothing; empty means only that a search found it (ADR 0009).
    library_added_at: Mapped[datetime | None] = mapped_column(UtcDateTime, index=True)

    identifiers: Mapped[list["PaperIdentifier"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    authors: Mapped[list["PaperAuthor"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperAuthor.position"
    )


class PaperIdentifier(TimestampMixin, Base):
    __tablename__ = "paper_identifier"
    __table_args__ = (UniqueConstraint("scheme", "value"),)

    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="CASCADE"), index=True)
    scheme: Mapped[IdentifierScheme] = mapped_column(enum_type(IdentifierScheme, "scheme"))
    value: Mapped[str] = mapped_column(String(256))

    paper: Mapped[Paper] = relationship(back_populates="identifiers")


class PaperRelation(TimestampMixin, Base):
    __tablename__ = "paper_relation"
    __table_args__ = (
        UniqueConstraint("from_paper_id", "to_paper_id", "kind"),
        CheckConstraint("from_paper_id != to_paper_id", name="not_self"),
    )

    from_paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="CASCADE"))
    to_paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="CASCADE"), index=True)
    kind: Mapped[RelationKind] = mapped_column(enum_type(RelationKind, "kind"))


class Author(TimestampMixin, Base):
    __tablename__ = "author"

    display_name: Mapped[str] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    given: Mapped[str | None] = mapped_column(Text)
    orcid: Mapped[str | None] = mapped_column(String(19), unique=True)


class PaperAuthor(TimestampMixin, Base):
    __tablename__ = "paper_author"
    __table_args__ = (
        UniqueConstraint("paper_id", "position"),
        CheckConstraint("position >= 0", name="position"),
    )

    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="CASCADE"))
    # RESTRICT: an author row outlives its papers; clean-up is explicit.
    author_id: Mapped[str] = mapped_column(ForeignKey("author.id", ondelete="RESTRICT"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    affiliation_raw: Mapped[str | None] = mapped_column(Text)

    paper: Mapped[Paper] = relationship(back_populates="authors")
    author: Mapped[Author] = relationship()


class Collection(TimestampMixin, Base):
    __tablename__ = "collection"

    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("collection.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    # System collections (e.g. the inbox) are named by the UI, not by `name`.
    is_system: Mapped[bool] = mapped_column(default=False)


class CollectionPaper(TimestampMixin, Base):
    __tablename__ = "collection_paper"
    __table_args__ = (UniqueConstraint("collection_id", "paper_id"),)

    collection_id: Mapped[str] = mapped_column(ForeignKey("collection.id", ondelete="CASCADE"))
    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="CASCADE"), index=True)


class Tag(TimestampMixin, Base):
    __tablename__ = "tag"

    name: Mapped[str] = mapped_column(Text, unique=True)
    color: Mapped[str | None] = mapped_column(String(16))


class PaperTag(TimestampMixin, Base):
    __tablename__ = "paper_tag"
    __table_args__ = (UniqueConstraint("paper_id", "tag_id"),)

    paper_id: Mapped[str] = mapped_column(ForeignKey("paper.id", ondelete="CASCADE"))
    tag_id: Mapped[str] = mapped_column(ForeignKey("tag.id", ondelete="CASCADE"), index=True)


class SmartCollection(TimestampMixin, Base):
    __tablename__ = "smart_collection"

    name: Mapped[str] = mapped_column(Text)
    # A versioned filter DSL, compiled to a query (Task 19+).
    filter_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    filter_version: Mapped[int] = mapped_column(Integer, default=1)
