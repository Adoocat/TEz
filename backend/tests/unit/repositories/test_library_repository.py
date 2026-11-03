import uuid
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from tests.unit.repositories.conftest import violates
from tez.core.errors import ErrorCode, TezError
from tez.modules.files.repository import FilesRepository
from tez.modules.library.models import (
    Author,
    IdentifierScheme,
    PaperAuthor,
    PaperIdentifier,
    ReadingStatus,
    RelationKind,
)
from tez.modules.library.repository import AuthorInput, LibraryRepository
from tez.modules.reviews.models import RecordOrigin, ReviewMethod
from tez.modules.reviews.repository import ReviewsRepository

SHA = "a" * 64


@pytest.fixture
def repo(session: Session) -> LibraryRepository:
    return LibraryRepository(session)


def add(repo: LibraryRepository, title: str = "LLM-based Code Review", **kw: Any) -> str:
    return repo.add_paper(title, **kw).id


# --- papers ---------------------------------------------------------------------------


def test_add_paper_fills_ids_timestamps_and_normalized_title(repo: LibraryRepository) -> None:
    paper = repo.add_paper("Kod İnceleme: LLM'lerle IŞIK Hızında!", year=2025)

    assert uuid.UUID(paper.id).version == 7
    assert paper.title_norm == "kod inceleme llm lerle isik hizinda"
    assert paper.reading_status is ReadingStatus.UNREAD
    assert paper.created_at.tzinfo is not None
    assert paper.created_at == paper.updated_at
    assert paper.deleted_at is None


def test_identifiers_and_ordered_authors(repo: LibraryRepository, session: Session) -> None:
    paper = repo.add_paper(
        "A Survey",
        identifiers=[(IdentifierScheme.DOI, "10.1145/123"), (IdentifierScheme.ARXIV, "2401.00001")],
        authors=[
            AuthorInput(display_name="Grace Hopper", family="Hopper", given="Grace"),
            AuthorInput(display_name="Ada Lovelace", family="Lovelace", given="Ada"),
        ],
    )
    session.flush()
    session.expire_all()

    reloaded = repo.get_paper(paper.id)
    assert reloaded is not None
    assert {(i.scheme, i.value) for i in reloaded.identifiers} == {
        (IdentifierScheme.DOI, "10.1145/123"),
        (IdentifierScheme.ARXIV, "2401.00001"),
    }
    assert [link.author.display_name for link in reloaded.authors] == [
        "Grace Hopper",
        "Ada Lovelace",
    ]
    assert [link.position for link in reloaded.authors] == [0, 1]


def test_author_with_the_same_orcid_is_reused(repo: LibraryRepository, session: Session) -> None:
    ada = AuthorInput(display_name="Ada Lovelace", orcid="0000-0002-1825-0097")
    repo.add_paper("First", authors=[ada])
    repo.add_paper("Second", authors=[AuthorInput(display_name="A. Lovelace", orcid=ada.orcid)])
    repo.add_paper("Third", authors=[AuthorInput(display_name="Ada Lovelace")])  # no ORCID
    session.flush()

    names = session.scalars(select(Author.display_name).order_by(Author.created_at)).all()
    assert names == ["Ada Lovelace", "Ada Lovelace"]


def test_find_by_identifier(repo: LibraryRepository) -> None:
    paper = repo.add_paper("X", identifiers=[(IdentifierScheme.DOI, "10.1/x")])

    assert repo.find_by_identifier(IdentifierScheme.DOI, "10.1/x") is paper
    assert repo.find_by_identifier(IdentifierScheme.DOI, "10.1/y") is None
    assert repo.find_by_identifier(IdentifierScheme.ARXIV, "10.1/x") is None


def test_soft_delete_and_restore(repo: LibraryRepository) -> None:
    keep = add(repo, "Keep")
    gone = add(repo, "Gone")

    repo.soft_delete(gone)

    assert [p.id for p in repo.list_papers()] == [keep]
    assert repo.get_paper(gone) is None
    deleted = repo.get_paper(gone, include_deleted=True)
    assert deleted is not None
    assert deleted.deleted_at is not None
    assert {p.id for p in repo.list_papers(include_deleted=True)} == {keep, gone}

    repo.restore(gone)
    assert [p.id for p in repo.list_papers()] == [keep, gone]


def test_updated_at_moves_on_change(repo: LibraryRepository, session: Session) -> None:
    paper = repo.add_paper("X")
    session.flush()
    created = paper.created_at

    paper.reading_status = ReadingStatus.READ
    session.flush()

    assert paper.created_at == created
    assert paper.updated_at > created


def test_relation_between_versions(repo: LibraryRepository) -> None:
    preprint = add(repo, "Preprint")
    published = add(repo, "Published")

    relation = repo.add_relation(preprint, published, RelationKind.VERSION_OF)

    assert (relation.from_paper_id, relation.to_paper_id) == (preprint, published)


# --- collections and tags ---------------------------------------------------------------


def test_collection_tree(repo: LibraryRepository) -> None:
    thesis = repo.add_collection("Tez")
    chapter2 = repo.add_collection("Bölüm 2", parent_id=thesis.id, sort_order=2)
    chapter1 = repo.add_collection("Bölüm 1", parent_id=thesis.id, sort_order=1)
    inbox = repo.add_collection("inbox", is_system=True)

    assert [c.id for c in repo.child_collections(None)] == [thesis.id, inbox.id]
    assert [c.id for c in repo.child_collections(thesis.id)] == [chapter1.id, chapter2.id]

    repo.move_collection(chapter2.id, None)
    assert [c.id for c in repo.child_collections(thesis.id)] == [chapter1.id]


def test_collection_cannot_move_under_itself(repo: LibraryRepository) -> None:
    a = repo.add_collection("A")
    b = repo.add_collection("B", parent_id=a.id)
    c = repo.add_collection("C", parent_id=b.id)

    for target in (a.id, c.id):
        with pytest.raises(TezError) as exc:
            repo.move_collection(a.id, target)
        assert exc.value.code is ErrorCode.COLLECTION_CYCLE


def test_papers_in_collections_are_idempotent(repo: LibraryRepository) -> None:
    col = repo.add_collection("Okunacaklar")
    paper = add(repo)

    repo.add_to_collection(col.id, paper)
    repo.add_to_collection(col.id, paper)
    assert [p.id for p in repo.papers_in_collection(col.id)] == [paper]

    repo.remove_from_collection(col.id, paper)
    repo.remove_from_collection(col.id, paper)
    assert repo.papers_in_collection(col.id) == []


def test_tags(repo: LibraryRepository) -> None:
    paper = add(repo)
    important = repo.add_tag("önemli", color="#dc2626")
    method = repo.add_tag("yöntem")

    repo.tag_paper(paper, important.id)
    repo.tag_paper(paper, important.id)
    repo.tag_paper(paper, method.id)
    assert [t.name for t in repo.tags_of(paper)] == ["önemli", "yöntem"]

    repo.untag_paper(paper, important.id)
    assert [t.name for t in repo.tags_of(paper)] == ["yöntem"]


def test_smart_collection_keeps_its_filter(repo: LibraryRepository) -> None:
    smart = repo.add_smart_collection("2023+", {"op": "gte", "field": "year", "value": 2023})

    assert smart.filter_json == {"op": "gte", "field": "year", "value": 2023}
    assert smart.filter_version == 1


# --- constraints ------------------------------------------------------------------------


def test_citekey_is_unique(repo: LibraryRepository, session: Session) -> None:
    add(repo, "A", citekey="kim2024")
    add(repo, "B")  # NULL citekeys do not collide
    add(repo, "C")
    session.flush()

    assert "UNIQUE" in violates(
        session,
        "INSERT INTO paper (id, title, title_norm, reading_status, retraction_status, citekey,"
        " created_at, updated_at)"
        " VALUES ('x', 'D', 'd', 'unread', 'none', 'kim2024', 'now', 'now')",
    )


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("reading_status", "skimmed"),
        ("retraction_status", "maybe"),
        ("venue_type", "blog"),
        ("citation_count", -1),
    ],
)
def test_paper_checks(session: Session, column: str, value: object) -> None:
    values: dict[str, object] = {
        "reading_status": "unread",
        "retraction_status": "none",
        "venue_type": None,
        "citation_count": None,
    }
    values[column] = value

    assert "CHECK" in violates(
        session,
        "INSERT INTO paper (id, title, title_norm, reading_status, retraction_status, venue_type,"
        " citation_count, created_at, updated_at) VALUES ('x', 'T', 't', :reading_status,"
        " :retraction_status, :venue_type, :citation_count, 'now', 'now')",
        **values,
    )


def test_identifier_is_unique_per_scheme(repo: LibraryRepository, session: Session) -> None:
    a = add(repo, "A", identifiers=[(IdentifierScheme.DOI, "10.1/x")])
    b = add(repo, "B", identifiers=[(IdentifierScheme.ARXIV, "10.1/x")])  # other scheme: fine
    session.flush()

    message = violates(
        session,
        "INSERT INTO paper_identifier (id, paper_id, scheme, value, created_at, updated_at)"
        " VALUES ('x', :paper, 'doi', '10.1/x', 'now', 'now')",
        paper=b,
    )
    assert "UNIQUE" in message
    assert a != b


def test_identifier_scheme_is_checked(repo: LibraryRepository, session: Session) -> None:
    paper = add(repo)
    session.flush()

    assert "CHECK" in violates(
        session,
        "INSERT INTO paper_identifier (id, paper_id, scheme, value, created_at, updated_at)"
        " VALUES ('x', :paper, 'isni', 'v', 'now', 'now')",
        paper=paper,
    )


def test_identifier_needs_an_existing_paper(session: Session) -> None:
    assert "FOREIGN KEY" in violates(
        session,
        "INSERT INTO paper_identifier (id, paper_id, scheme, value, created_at, updated_at)"
        " VALUES ('x', 'no-such-paper', 'doi', 'v', 'now', 'now')",
    )


def test_paper_cannot_relate_to_itself(repo: LibraryRepository, session: Session) -> None:
    paper = add(repo)
    session.flush()

    assert "CHECK" in violates(
        session,
        "INSERT INTO paper_relation (id, from_paper_id, to_paper_id, kind, created_at,"
        " updated_at) VALUES ('x', :p, :p, 'version_of', 'now', 'now')",
        p=paper,
    )


def test_author_positions_are_unique_per_paper(repo: LibraryRepository, session: Session) -> None:
    paper = repo.add_paper("X", authors=[AuthorInput(display_name="A")])
    session.flush()
    author_id = paper.authors[0].author_id

    assert "UNIQUE" in violates(
        session,
        "INSERT INTO paper_author (id, paper_id, author_id, position, created_at, updated_at)"
        " VALUES ('x', :paper, :author, 0, 'now', 'now')",
        paper=paper.id,
        author=author_id,
    )


def test_tag_names_are_unique(repo: LibraryRepository, session: Session) -> None:
    repo.add_tag("önemli")
    session.flush()

    assert "UNIQUE" in violates(
        session,
        "INSERT INTO tag (id, name, created_at, updated_at) VALUES ('x', 'önemli', 'now', 'now')",
    )


def test_hard_delete_cascades_to_links_but_keeps_authors(
    repo: LibraryRepository, session: Session
) -> None:
    paper = repo.add_paper(
        "X",
        identifiers=[(IdentifierScheme.DOI, "10.1/x")],
        authors=[AuthorInput(display_name="A")],
    )
    col = repo.add_collection("C")
    tag = repo.add_tag("t")
    repo.add_to_collection(col.id, paper.id)
    repo.tag_paper(paper.id, tag.id)
    session.flush()

    session.execute(text("DELETE FROM paper WHERE id = :id"), {"id": paper.id})

    for table in ("paper_identifier", "paper_author", "collection_paper", "paper_tag"):
        assert session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0, table
    assert session.scalar(select(Author.id)) is not None
    assert session.scalar(select(PaperIdentifier.id)) is None
    assert session.scalar(select(PaperAuthor.id)) is None


def test_paper_with_a_pdf_cannot_be_hard_deleted(repo: LibraryRepository, session: Session) -> None:
    paper = add(repo)
    FilesRepository(session).add_attachment(paper, rel_path="files/aa/x.pdf", sha256=SHA)
    session.flush()

    assert "FOREIGN KEY" in violates(session, "DELETE FROM paper WHERE id = :id", id=paper)


def test_paper_in_a_review_cannot_be_hard_deleted(
    repo: LibraryRepository, session: Session
) -> None:
    paper = add(repo)
    reviews = ReviewsRepository(session)
    review = reviews.add_review("SLR", method=ReviewMethod.KITCHENHAM_SLR)
    reviews.add_record(review.id, paper, RecordOrigin.DATABASE)
    session.flush()

    assert "FOREIGN KEY" in violates(session, "DELETE FROM paper WHERE id = :id", id=paper)


def test_deleting_a_collection_deletes_its_subtree(
    repo: LibraryRepository, session: Session
) -> None:
    parent = repo.add_collection("P")
    child = repo.add_collection("C", parent_id=parent.id)
    repo.add_collection("G", parent_id=child.id)
    session.flush()

    session.execute(text("DELETE FROM collection WHERE id = :id"), {"id": parent.id})

    assert session.execute(text("SELECT count(*) FROM collection")).scalar_one() == 0
