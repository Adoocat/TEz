"""Search in notes: the `note_fts` FTS5 table, folded like `paper_fts` (ADR 0014)."""

from sqlalchemy import Connection, text

from tez.modules.notes.links import plain_text
from tez.shared.text import fold
from tez.shared.textsearch import Term, expression

TABLE = "note_fts"
_LIMIT = 200


def forget(conn: Connection, note_id: str) -> None:
    conn.execute(text(f"DELETE FROM {TABLE} WHERE note_id = :id"), {"id": note_id})


def index(conn: Connection, note_id: str, title: str, body: str) -> None:
    forget(conn, note_id)
    conn.execute(
        text(f"INSERT INTO {TABLE} (note_id, title, body) VALUES (:id, :title, :body)"),
        {"id": note_id, "title": fold(title), "body": fold(plain_text(body))},
    )


def find(conn: Connection, terms: list[Term]) -> list[str]:
    """Note ids, best first; a word in the title weighs most."""
    rows = conn.execute(
        text(
            f"SELECT note_id FROM {TABLE} WHERE {TABLE} MATCH :expression "
            f"ORDER BY bm25({TABLE}, 0.0, 8.0, 1.0) LIMIT :limit"
        ),
        {"expression": expression(terms), "limit": _LIMIT},
    )
    return [row[0] for row in rows]
