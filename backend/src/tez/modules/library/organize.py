"""Organizing the library: the collection tree, tags and reading status (plan, Task 18).

A paper may sit in any number of collections and carry any number of tags. Deleting a
collection deletes its sub-collections but never a paper: papers live in the library, and
collections only point at them. The inbox is a system collection: it cannot be renamed, moved
or deleted.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.files import service as files_service
from tez.modules.files.models import TextStatus
from tez.modules.library.models import (
    Collection,
    CollectionPaper,
    IdentifierScheme,
    Paper,
    PaperTag,
    ReadingStatus,
    Tag,
)
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.schemas import (
    ChangeCount,
    CollectionView,
    LibraryPaperRow,
    TagView,
)
from tez.shared.text import fold

_BATCH = 500


def _batches(ids: Sequence[str]) -> Iterable[list[str]]:
    for start in range(0, len(ids), _BATCH):
        yield list(ids[start : start + _BATCH])


def _live_papers() -> list[ColumnElement[bool]]:
    """Papers that count: kept in the library and not in the trash."""
    return [Paper.library_added_at.is_not(None), Paper.deleted_at.is_(None)]


# --- collections ----------------------------------------------------------------------


def _collection_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(CollectionPaper.collection_id, func.count())
        .join(Paper, Paper.id == CollectionPaper.paper_id)
        .where(*_live_papers())
        .group_by(CollectionPaper.collection_id)
    )
    return {collection_id: count for collection_id, count in rows}


def _collection_view(collection: Collection, counts: dict[str, int]) -> CollectionView:
    return CollectionView(
        id=collection.id,
        parent_id=collection.parent_id,
        name=collection.name,
        sort_order=collection.sort_order,
        is_system=collection.is_system,
        paper_count=counts.get(collection.id, 0),
    )


def list_collections(db: Database) -> list[CollectionView]:
    """Every collection, parents before children; siblings alphabetical, Turkish-aware."""
    with db.session() as session:
        collections = list(session.scalars(select(Collection)))
        counts = _collection_counts(session)
    by_parent: dict[str | None, list[Collection]] = defaultdict(list)
    for collection in collections:
        by_parent[collection.parent_id].append(collection)
    ordered: list[CollectionView] = []

    def walk(parent: str | None) -> None:
        children = sorted(by_parent[parent], key=lambda c: (c.sort_order, fold(c.name)))
        for child in children:
            ordered.append(_collection_view(child, counts))
            walk(child.id)

    walk(None)
    return ordered


def _collection(session: Session, collection_id: str) -> Collection:
    collection = session.get(Collection, collection_id)
    if collection is None:
        params = {"collection_id": collection_id}
        raise TezError(ErrorCode.COLLECTION_NOT_FOUND, params, status=404)
    return collection


def _check_name_free(
    session: Session, name: str, parent_id: str | None, *, exclude: str | None = None
) -> None:
    same_parent = (
        Collection.parent_id.is_(None) if parent_id is None else Collection.parent_id == parent_id
    )
    siblings = session.scalars(select(Collection).where(same_parent))
    if any(fold(s.name) == fold(name) and s.id != exclude for s in siblings):
        raise TezError(ErrorCode.COLLECTION_NAME_TAKEN, {"name": name}, status=409)


def _members(session: Session, collection_id: str) -> set[str]:
    query = select(CollectionPaper.paper_id).where(CollectionPaper.collection_id == collection_id)
    return set(session.scalars(query))


def create_collection(db: Database, name: str, parent_id: str | None) -> CollectionView:
    with db.write_session() as session:
        if parent_id is not None:
            _collection(session, parent_id)
        _check_name_free(session, name, parent_id)
        collection = LibraryRepository(session).add_collection(name, parent_id=parent_id)
        return _collection_view(collection, {})


def update_collection(
    db: Database, collection_id: str, changes: dict[str, str | None]
) -> CollectionView:
    """Rename and/or move. `changes` holds only the fields the client sent."""
    with db.write_session() as session:
        collection = _collection(session, collection_id)
        if collection.is_system:
            raise TezError(
                ErrorCode.COLLECTION_SYSTEM, {"collection_id": collection_id}, status=409
            )
        parent_id = changes.get("parent_id", collection.parent_id)
        name = changes.get("name") or collection.name
        if "parent_id" in changes and parent_id is not None:
            _collection(session, parent_id)
        _check_name_free(session, name, parent_id, exclude=collection_id)
        if "parent_id" in changes and parent_id != collection.parent_id:
            try:
                LibraryRepository(session).move_collection(collection_id, parent_id)
            except TezError as error:
                error.status = 409
                raise
        collection.name = name
        session.flush()
        return _collection_view(collection, _collection_counts(session))


def delete_collection(db: Database, collection_id: str) -> None:
    with db.write_session() as session:
        collection = _collection(session, collection_id)
        if collection.is_system:
            raise TezError(
                ErrorCode.COLLECTION_SYSTEM, {"collection_id": collection_id}, status=409
            )
        # Sub-collections and memberships go by ON DELETE CASCADE; papers stay.
        session.delete(collection)


def _require_papers(session: Session, paper_ids: Sequence[str]) -> list[str]:
    wanted = list(dict.fromkeys(paper_ids))
    if missing := set(wanted) - PaperService(session).existing_ids(wanted):
        raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": sorted(missing)}, status=404)
    return wanted


def add_to_collection(db: Database, collection_id: str, paper_ids: Sequence[str]) -> ChangeCount:
    with db.write_session() as session:
        _collection(session, collection_id)
        wanted = _require_papers(session, paper_ids)
        present = _members(session, collection_id)
        new = [p for p in wanted if p not in present]
        session.add_all(CollectionPaper(collection_id=collection_id, paper_id=p) for p in new)
        # Filing a paper keeps it: a search candidate dropped on a collection joins the library.
        PaperService(session).keep(new)
        return ChangeCount(changed=len(new), unchanged=len(wanted) - len(new))


def remove_from_collection(
    db: Database, collection_id: str, paper_ids: Sequence[str]
) -> ChangeCount:
    with db.write_session() as session:
        _collection(session, collection_id)
        wanted = list(dict.fromkeys(paper_ids))
        present = _members(session, collection_id)
        removed = [p for p in wanted if p in present]
        repository = LibraryRepository(session)
        for paper_id in removed:
            repository.remove_from_collection(collection_id, paper_id)
        return ChangeCount(changed=len(removed), unchanged=len(wanted) - len(removed))


# --- tags -----------------------------------------------------------------------------


def _tag_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(PaperTag.tag_id, func.count())
        .join(Paper, Paper.id == PaperTag.paper_id)
        .where(*_live_papers())
        .group_by(PaperTag.tag_id)
    )
    return {tag_id: count for tag_id, count in rows}


def _tag_view(tag: Tag, counts: dict[str, int]) -> TagView:
    return TagView(id=tag.id, name=tag.name, color=tag.color, paper_count=counts.get(tag.id, 0))


def list_tags(db: Database) -> list[TagView]:
    with db.session() as session:
        tags = sorted(session.scalars(select(Tag)), key=lambda t: fold(t.name))
        counts = _tag_counts(session)
        return [_tag_view(tag, counts) for tag in tags]


def _tag(session: Session, tag_id: str) -> Tag:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise TezError(ErrorCode.TAG_NOT_FOUND, {"tag_id": tag_id}, status=404)
    return tag


def _check_tag_free(session: Session, name: str, *, exclude: str | None = None) -> None:
    if any(fold(t.name) == fold(name) and t.id != exclude for t in session.scalars(select(Tag))):
        raise TezError(ErrorCode.TAG_NAME_TAKEN, {"name": name}, status=409)


def create_tag(db: Database, name: str, color: str | None) -> TagView:
    with db.write_session() as session:
        _check_tag_free(session, name)
        return _tag_view(LibraryRepository(session).add_tag(name, color=color), {})


def update_tag(db: Database, tag_id: str, changes: dict[str, str | None]) -> TagView:
    with db.write_session() as session:
        tag = _tag(session, tag_id)
        if (name := changes.get("name")) is not None:
            _check_tag_free(session, name, exclude=tag_id)
            tag.name = name
        if "color" in changes:
            tag.color = changes["color"]
        session.flush()
        return _tag_view(tag, _tag_counts(session))


def delete_tag(db: Database, tag_id: str) -> None:
    with db.write_session() as session:
        session.delete(_tag(session, tag_id))


def tag_papers(db: Database, tag_id: str, paper_ids: Sequence[str]) -> ChangeCount:
    with db.write_session() as session:
        _tag(session, tag_id)
        wanted = _require_papers(session, paper_ids)
        present = set(session.scalars(select(PaperTag.paper_id).where(PaperTag.tag_id == tag_id)))
        new = [p for p in wanted if p not in present]
        session.add_all(PaperTag(tag_id=tag_id, paper_id=p) for p in new)
        return ChangeCount(changed=len(new), unchanged=len(wanted) - len(new))


def untag_papers(db: Database, tag_id: str, paper_ids: Sequence[str]) -> ChangeCount:
    with db.write_session() as session:
        _tag(session, tag_id)
        wanted = list(dict.fromkeys(paper_ids))
        present = set(session.scalars(select(PaperTag.paper_id).where(PaperTag.tag_id == tag_id)))
        removed = [p for p in wanted if p in present]
        repository = LibraryRepository(session)
        for paper_id in removed:
            repository.untag_paper(paper_id, tag_id)
        return ChangeCount(changed=len(removed), unchanged=len(wanted) - len(removed))


# --- reading status -------------------------------------------------------------------


def set_reading_status(
    db: Database, paper_ids: Sequence[str], status: ReadingStatus
) -> ChangeCount:
    with db.write_session() as session:
        wanted = _require_papers(session, paper_ids)
        changed = 0
        for batch in _batches(wanted):
            for paper in session.scalars(select(Paper).where(Paper.id.in_(batch))):
                if paper.reading_status is not status:
                    paper.reading_status = status
                    changed += 1
        return ChangeCount(changed=changed, unchanged=len(wanted) - changed)


# --- the library list -----------------------------------------------------------------


def _memberships(
    session: Session, model: type[CollectionPaper] | type[PaperTag], paper_ids: Sequence[str]
) -> dict[str, list[str]]:
    column = CollectionPaper.collection_id if model is CollectionPaper else PaperTag.tag_id
    owner = CollectionPaper.paper_id if model is CollectionPaper else PaperTag.paper_id
    found: dict[str, list[str]] = defaultdict(list)
    for batch in _batches(paper_ids):
        for paper_id, other in session.execute(select(owner, column).where(owner.in_(batch))):
            found[paper_id].append(other)
    return found


def _row(
    card: PaperCard,
    tags: dict[str, list[str]],
    collections: dict[str, list[str]],
    pdfs: dict[str, TextStatus],
) -> LibraryPaperRow:
    paper = card.paper
    pdf = pdfs.get(paper.id)
    return LibraryPaperRow(
        id=paper.id,
        title=paper.title,
        first_author=card.first_author.display_name if card.first_author else None,
        author_count=card.author_count,
        year=paper.year,
        venue=paper.venue,
        venue_type=paper.venue_type,
        doi=card.identifiers.get(IdentifierScheme.DOI),
        citekey=paper.citekey,
        citation_count=paper.citation_count,
        reading_status=paper.reading_status,
        tag_ids=tags.get(paper.id, []),
        collection_ids=collections.get(paper.id, []),
        pdf="none" if pdf is None else pdf.value,
        added_at=paper.library_added_at,
    )


def list_papers(
    db: Database, *, collection_id: str | None = None, tag_id: str | None = None
) -> list[LibraryPaperRow]:
    """Papers in the library (not candidates, not the trash), newest first."""
    with db.session() as session:
        conditions = _live_papers()
        if collection_id is not None:
            conditions.append(
                Paper.id.in_(
                    select(CollectionPaper.paper_id).where(
                        CollectionPaper.collection_id == collection_id
                    )
                )
            )
        if tag_id is not None:
            tagged = select(PaperTag.paper_id).where(PaperTag.tag_id == tag_id)
            conditions.append(Paper.id.in_(tagged))
        cards = PaperService(session).cards_where(*conditions)
        ids = [card.paper.id for card in cards]
        tags = _memberships(session, PaperTag, ids)
        collections = _memberships(session, CollectionPaper, ids)
        pdfs = files_service.pdf_states(session, ids)
        rows = [_row(card, tags, collections, pdfs) for card in cards]
    rows.sort(key=lambda row: (row.added_at is not None, row.added_at), reverse=True)
    return rows
