from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from tez.core.db import utcnow
from tez.modules.notes import search_index
from tez.modules.notes.models import LinkTarget, Note, NoteLink


class NotesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, note: Note) -> Note:
        self.session.add(note)
        self.session.flush()
        return note

    def get(self, note_id: str, *, deleted: bool = False) -> Note | None:
        note = self.session.get(Note, note_id)
        if note is None or (note.deleted_at is not None and not deleted):
            return None
        return note

    def live(self) -> list[Note]:
        return list(
            self.session.scalars(
                select(Note).where(Note.deleted_at.is_(None)).order_by(Note.created_at)
            )
        )

    def many(self, note_ids: Iterable[str]) -> dict[str, Note]:
        found = self.session.scalars(
            select(Note).where(Note.id.in_(set(note_ids)), Note.deleted_at.is_(None))
        )
        return {note.id: note for note in found}

    def children(self, note_id: str) -> list[Note]:
        return list(
            self.session.scalars(
                select(Note).where(Note.parent_id == note_id, Note.deleted_at.is_(None))
            )
        )

    def set_links(self, note_id: str, links: Sequence[NoteLink]) -> None:
        self.session.execute(delete(NoteLink).where(NoteLink.source_note_id == note_id))
        self.session.add_all(links)
        self.session.flush()

    def links_of(self, note_id: str) -> list[NoteLink]:
        return list(
            self.session.scalars(
                select(NoteLink).where(NoteLink.source_note_id == note_id).order_by(NoteLink.ord)
            )
        )

    def unresolved(self) -> list[NoteLink]:
        return list(self.session.scalars(select(NoteLink).where(NoteLink.target_id.is_(None))))

    def linking_to(self, target: LinkTarget, target_ids: Iterable[str]) -> list[Note]:
        """Notes with a link to any of these, newest change first."""
        return list(
            self.session.scalars(
                select(Note)
                .where(
                    Note.deleted_at.is_(None),
                    Note.id.in_(
                        select(NoteLink.source_note_id).where(
                            NoteLink.target_type == target,
                            NoteLink.target_id.in_(set(target_ids)),
                        )
                    ),
                )
                .order_by(Note.updated_at.desc())
            )
        )

    def about_paper(self, paper_id: str) -> list[Note]:
        return list(
            self.session.scalars(
                select(Note)
                .where(Note.paper_id == paper_id, Note.deleted_at.is_(None))
                .order_by(Note.updated_at.desc())
            )
        )

    def trash(self, note: Note) -> None:
        note.deleted_at = utcnow()
        search_index.forget(self.session.connection(), note.id)
        self.session.flush()

    def index(self, note: Note) -> None:
        search_index.index(self.session.connection(), note.id, note.title, note.body_md)
