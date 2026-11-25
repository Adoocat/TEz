"""Notes: Markdown with links to notes, papers and places in PDFs (plan, Task 48; ADR 0034)."""

import re
from collections.abc import Iterable, Sequence

from sqlalchemy.orm import Session

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.anchors import service as anchors_service
from tez.modules.library.models import Paper
from tez.modules.library.paper_service import PaperCard, PaperService
from tez.modules.notes import search_index
from tez.modules.notes.links import links_in, plain_text, retarget
from tez.modules.notes.models import LinkTarget, Note, NoteLink
from tez.modules.notes.repository import NotesRepository
from tez.modules.notes.schemas import (
    Backlink,
    LinkSuggestion,
    NoteCreate,
    NoteHit,
    NoteHitPart,
    NoteLinkView,
    NotePatch,
    NoteSummary,
    NoteView,
)
from tez.modules.reviews import service as reviews_service
from tez.shared.text import fold
from tez.shared.textsearch import parse, passage

_SUGGESTIONS = 20
# Characters of the note shown around a link to this one.
_AROUND_LINK = 90


def _get(session: Session, note_id: str, *, deleted: bool = False) -> Note:
    note = NotesRepository(session).get(note_id, deleted=deleted)
    if note is None:
        raise TezError(ErrorCode.NOTE_NOT_FOUND, {"note_id": note_id}, status=404)
    return note


def _summary(note: Note) -> NoteSummary:
    return NoteSummary(
        id=note.id,
        title=note.title,
        parent_id=note.parent_id,
        paper_id=note.paper_id,
        review_id=note.review_id,
        version=note.version,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# --- links -----------------------------------------------------------------------------


class _Names:
    """What a typed `[[name]]` can mean: a note's title, or a paper's citation key or title."""

    def __init__(self, session: Session) -> None:
        self._found: dict[str, tuple[LinkTarget, str]] = {}
        papers = PaperService(session).cards(PaperService(session).library_ids()).values()
        # Later entries win: citation keys over titles, notes over papers.
        for card in papers:
            self._found[fold(card.paper.title).strip()] = (LinkTarget.PAPER, card.paper.id)
        for card in papers:
            if card.paper.citekey:
                self._found[fold(card.paper.citekey)] = (LinkTarget.PAPER, card.paper.id)
        for note in reversed(NotesRepository(session).live()):
            self._found[fold(note.title).strip()] = (LinkTarget.NOTE, note.id)

    def get(self, name: str) -> tuple[LinkTarget, str] | None:
        return self._found.get(fold(name).strip())


def _save_links(session: Session, note: Note) -> None:
    """Read the note's links from its text and store them in place of the old ones."""
    written = list(links_in(note.body_md))
    names = _Names(session) if any(link.target_id is None for link in written) else None
    links: list[NoteLink] = []
    for order, link in enumerate(written):
        target = (link.target_type, link.target_id)
        if link.target_id is None and names is not None:
            target = names.get(link.label) or (None, None)
        links.append(
            NoteLink(
                source_note_id=note.id,
                ord=order,
                target_type=target[0],
                target_id=target[1],
                label=link.label,
            )
        )
    NotesRepository(session).set_links(note.id, links)


def _resolve_waiting(session: Session, note: Note) -> None:
    """A `[[name]]` written before its note existed finds it now."""
    name = fold(note.title).strip()
    for link in NotesRepository(session).unresolved():
        if fold(link.label).strip() == name:
            link.target_type, link.target_id = LinkTarget.NOTE, note.id
    session.flush()


def _follow_rename(session: Session, note: Note, old_title: str) -> None:
    """Notes that wrote `[[Old title]]` keep their link: it becomes one by id."""
    repository = NotesRepository(session)
    for source in repository.linking_to(LinkTarget.NOTE, [note.id]):
        for link in repository.links_of(source.id):
            if link.target_id != note.id or fold(link.label) != fold(old_title):
                continue
            body = retarget(source.body_md, link.label, note.title, LinkTarget.NOTE, note.id)
            if body != source.body_md:
                source.body_md = body
                source.version += 1
        _save_links(session, source)
        repository.index(source)


def _link_views(session: Session, links: Sequence[NoteLink]) -> list[NoteLinkView]:
    def ids(target: LinkTarget) -> set[str]:
        return {link.target_id for link in links if link.target_type is target and link.target_id}

    notes = NotesRepository(session).many(ids(LinkTarget.NOTE))
    papers = PaperService(session).cards(ids(LinkTarget.PAPER))
    anchors = anchors_service.by_id(session, ids(LinkTarget.ANCHOR))
    views: list[NoteLinkView] = []
    for link in links:
        target_id = link.target_id or ""
        title: str | None = None
        anchor = anchors.get(target_id)
        ok = False
        if (note := notes.get(target_id)) is not None:
            title, ok = note.title, True
        elif (card := papers.get(target_id)) is not None:
            title, ok = card.paper.title, card.paper.deleted_at is None
        elif anchor is not None:
            title, ok = anchor.paper.title, anchor.status != "lost"
        views.append(
            NoteLinkView(
                target_type=link.target_type,
                target_id=link.target_id,
                label=link.label,
                status="ok" if ok else "broken",
                title=title,
                anchor=anchor,
            )
        )
    return views


def _view(session: Session, note: Note) -> NoteView:
    links = NotesRepository(session).links_of(note.id)
    return NoteView(
        **_summary(note).model_dump(), body=note.body_md, links=_link_views(session, links)
    )


# --- notes -----------------------------------------------------------------------------


def _check_place(
    session: Session,
    db: Database,
    *,
    parent_id: str | None,
    paper_id: str | None,
    review_id: str | None,
) -> None:
    if parent_id is not None:
        _get(session, parent_id)
    if paper_id is not None and not PaperService(session).existing_ids([paper_id]):
        raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": [paper_id]}, status=404)
    if review_id is not None:
        reviews_service.get_review(db, review_id)


def list_notes(db: Database) -> list[NoteSummary]:
    """Every note, oldest first; the screen builds the tree from `parent_id`."""
    with db.session() as session:
        return [_summary(note) for note in NotesRepository(session).live()]


def get(db: Database, note_id: str) -> NoteView:
    with db.session() as session:
        return _view(session, _get(session, note_id))


def create(db: Database, body: NoteCreate) -> NoteView:
    with db.write_session() as session:
        _check_place(
            session,
            db,
            parent_id=body.parent_id,
            paper_id=body.paper_id,
            review_id=body.review_id,
        )
        repository = NotesRepository(session)
        note = repository.add(
            Note(
                title=body.title,
                body_md=body.body,
                parent_id=body.parent_id,
                paper_id=body.paper_id,
                review_id=body.review_id,
            )
        )
        _save_links(session, note)
        _resolve_waiting(session, note)
        repository.index(note)
        return _view(session, note)


def update(db: Database, note_id: str, body: NotePatch) -> NoteView:
    with db.write_session() as session:
        note = _get(session, note_id)
        if body.base_version is not None and body.base_version != note.version:
            raise TezError(
                ErrorCode.NOTE_CONFLICT,
                {"note_id": note_id, "version": note.version},
                status=409,
            )
        given = body.model_fields_set
        _check_place(
            session,
            db,
            parent_id=body.parent_id,
            paper_id=body.paper_id,
            review_id=body.review_id,
        )
        old_title = note.title
        if "parent_id" in given:
            _check_no_cycle(session, note, body.parent_id)
            note.parent_id = body.parent_id
        if "paper_id" in given:
            note.paper_id = body.paper_id
        if "review_id" in given:
            note.review_id = body.review_id
        if body.title is not None:
            note.title = body.title
        if body.body is not None:
            note.body_md = body.body
        note.version += 1
        session.flush()
        if body.body is not None:
            _save_links(session, note)
        if note.title != old_title:
            _follow_rename(session, note, old_title)
            _resolve_waiting(session, note)
        NotesRepository(session).index(note)
        return _view(session, note)


def append(db: Database, note_id: str, addition: str) -> NoteView:
    with db.write_session() as session:
        note = _get(session, note_id)
        before = note.body_md.rstrip()
        note.body_md = f"{before}\n\n{addition.strip()}\n" if before else f"{addition.strip()}\n"
        note.version += 1
        session.flush()
        _save_links(session, note)
        NotesRepository(session).index(note)
        return _view(session, note)


def _check_no_cycle(session: Session, note: Note, parent_id: str | None) -> None:
    ancestor = parent_id
    while ancestor is not None:
        if ancestor == note.id:
            raise TezError(ErrorCode.NOTE_CYCLE, {"note_id": note.id}, status=409)
        parent = NotesRepository(session).get(ancestor, deleted=True)
        ancestor = parent.parent_id if parent else None


def delete(db: Database, note_id: str) -> None:
    """To the trash. Notes inside it move up; links to it show as broken."""
    with db.write_session() as session:
        repository = NotesRepository(session)
        note = _get(session, note_id)
        for child in repository.children(note_id):
            child.parent_id = note.parent_id
        repository.trash(note)


def restore(db: Database, note_id: str) -> NoteView:
    with db.write_session() as session:
        note = _get(session, note_id, deleted=True)
        note.deleted_at = None
        if note.parent_id is not None and NotesRepository(session).get(note.parent_id) is None:
            note.parent_id = None
        session.flush()
        NotesRepository(session).index(note)
        return _view(session, note)


# --- looking up ------------------------------------------------------------------------


def _passage_with_link(body: str, target_ids: Iterable[str], names: Iterable[str]) -> str:
    """The text around the first link to the target, as it reads."""
    folded_names = {fold(name) for name in names}
    wanted = set(target_ids)
    for found in re.finditer(r"\]\(tez:\w+/([\w-]+)\)|\[\[([^\[\]\n]+)\]\]", body):
        hit = found[1] in wanted if found[1] else fold(found[2]).strip() in folded_names
        if not hit:
            continue
        start = max(0, found.start() - _AROUND_LINK)
        end = min(len(body), found.end() + _AROUND_LINK)
        text = " ".join(plain_text(body[start:end]).split())
        return ("…" if start else "") + text + ("…" if end < len(body) else "")
    return ""


def _backlinks(notes: Iterable[Note], target_ids: Iterable[str], *names: str) -> list[Backlink]:
    wanted = list(target_ids)
    return [
        Backlink(
            note_id=note.id,
            title=note.title,
            passage=_passage_with_link(note.body_md, wanted, names),
        )
        for note in notes
    ]


def backlinks(db: Database, note_id: str) -> list[Backlink]:
    with db.session() as session:
        note = _get(session, note_id)
        linking = NotesRepository(session).linking_to(LinkTarget.NOTE, [note_id])
        return _backlinks([n for n in linking if n.id != note_id], [note_id], note.title)


def of_paper(db: Database, paper_id: str) -> list[Backlink]:
    """Notes about a paper: attached to it, or linking to it or to a place in its PDFs."""
    with db.session() as session:
        repository = NotesRepository(session)
        cards = PaperService(session).cards([paper_id])
        if paper_id not in cards:
            raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": [paper_id]}, status=404)
        paper = cards[paper_id].paper
        anchors = anchors_service.ids_in_paper(session, paper_id)
        found: dict[str, Note] = {}
        for note in [
            *repository.about_paper(paper_id),
            *repository.linking_to(LinkTarget.PAPER, [paper_id]),
            *repository.linking_to(LinkTarget.ANCHOR, anchors),
        ]:
            found.setdefault(note.id, note)
        return _backlinks(
            found.values(), [paper_id, *anchors], paper.title, paper.citekey or paper.title
        )


def search(db: Database, query: str) -> list[NoteHit]:
    terms = parse(query)
    if not terms:
        return []
    with db.session() as session:
        ids = search_index.find(session.connection(), terms)
        notes = NotesRepository(session).many(ids)
        return [
            NoteHit(
                note_id=note_id,
                title=notes[note_id].title,
                passage=[
                    NoteHitPart(text=part.text, hit=part.hit)
                    for part in passage(" ".join(plain_text(notes[note_id].body_md).split()), terms)
                    if part.text
                ],
            )
            for note_id in ids
            if note_id in notes
        ]


def _byline(card: PaperCard) -> str | None:
    paper: Paper = card.paper
    family = None
    if card.first_author is not None:
        family = card.first_author.family or card.first_author.display_name
    parts = [family, str(paper.year) if paper.year else None]
    return " ".join(part for part in parts if part) or None


def suggest(db: Database, query: str) -> list[LinkSuggestion]:
    """What `[[` can link to: notes and library papers with every word of the query."""
    words = fold(query).split()
    with db.session() as session:
        service = PaperService(session)
        found: list[tuple[int, LinkSuggestion]] = []

        def consider(suggestion: LinkSuggestion, *texts: str | None) -> None:
            haystack = fold(" ".join(text for text in texts if text))
            if all(word in haystack for word in words):
                # The title begins with what was typed, then has it, then something else does.
                title = fold(suggestion.title)
                typed = " ".join(words)
                rank = 0 if title.startswith(typed) else 1 if typed in title else 2
                found.append((rank, suggestion))

        for note in NotesRepository(session).live():
            consider(
                LinkSuggestion(
                    target_type="note", target_id=note.id, title=note.title, detail=None
                ),
                note.title,
            )
        for card in service.cards(service.library_ids()).values():
            consider(
                LinkSuggestion(
                    target_type="paper",
                    target_id=card.paper.id,
                    title=card.paper.title,
                    detail=_byline(card),
                ),
                card.paper.title,
                card.paper.citekey,
                _byline(card),
            )
    found.sort(key=lambda item: (item[0], item[1].target_type, fold(item[1].title)))
    return [suggestion for _, suggestion in found[:_SUGGESTIONS]]
