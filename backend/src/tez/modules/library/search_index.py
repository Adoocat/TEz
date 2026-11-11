"""Metadata full-text search: the `paper_fts` FTS5 table, kept in step with `paper` (Task 19).

FTS5's own tokenizer folds Turkish wrongly ("I" is not "ı"), so the indexed text is folded here
with `tez.shared.text.fold`, and queries are folded the same way. The index is maintained after
every flush that touches a paper or its authors, in the same transaction, so it cannot drift
from what was committed. `ensure_complete` rebuilds it when a library opens with an index that
does not match (the first open after migration 0007, or a copy restored from elsewhere).
"""

import logging
import re
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection, event, text
from sqlalchemy.orm import Session, UOWTransaction

from tez.core.db import Database
from tez.modules.library.models import Paper, PaperAuthor, PaperIdentifier
from tez.shared.text import fold

logger = logging.getLogger(__name__)

TABLE = "paper_fts"
_BATCH = 400
_TOKEN = re.compile(r"\w+")
# bm25 weights per column: title, authors, abstract, venue, extra (identifiers, citekey, year).
_WEIGHTS = "10.0, 6.0, 1.0, 2.0, 4.0"
MAX_HITS = 5000


def _folded(value: str | None) -> str:
    return fold(value) if value else ""


def reindex(conn: Connection, paper_ids: Iterable[str]) -> None:
    """Write the index rows of these papers again from their current data."""
    ids = list(dict.fromkeys(paper_ids))
    for start in range(0, len(ids), _BATCH):
        batch = ids[start : start + _BATCH]
        marks = ", ".join(f":p{i}" for i in range(len(batch)))
        params = {f"p{i}": paper_id for i, paper_id in enumerate(batch)}
        conn.execute(text(f"DELETE FROM {TABLE} WHERE paper_id IN ({marks})"), params)
        papers = conn.execute(
            text(
                f"SELECT id, title, abstract, venue, year, citekey FROM paper WHERE id IN ({marks})"
            ),
            params,
        ).all()
        authors: dict[str, list[str]] = {}
        for paper_id, name in conn.execute(
            text(
                "SELECT pa.paper_id, a.display_name FROM paper_author pa "
                f"JOIN author a ON a.id = pa.author_id WHERE pa.paper_id IN ({marks}) "
                "ORDER BY pa.position"
            ),
            params,
        ):
            authors.setdefault(paper_id, []).append(name)
        identifiers: dict[str, list[str]] = {}
        for paper_id, value in conn.execute(
            text(f"SELECT paper_id, value FROM paper_identifier WHERE paper_id IN ({marks})"),
            params,
        ):
            identifiers.setdefault(paper_id, []).append(value)
        rows: list[dict[str, Any]] = []
        for paper_id, title, abstract, venue, year, citekey in papers:
            extra = " ".join([*identifiers.get(paper_id, []), citekey or "", str(year or "")])
            rows.append(
                {
                    "paper_id": paper_id,
                    "title": _folded(title),
                    "authors": _folded(" ; ".join(authors.get(paper_id, []))),
                    "abstract": _folded(abstract),
                    "venue": _folded(venue),
                    "extra": _folded(extra),
                }
            )
        if rows:
            conn.execute(
                text(
                    f"INSERT INTO {TABLE} (paper_id, title, authors, abstract, venue, extra) "
                    "VALUES (:paper_id, :title, :authors, :abstract, :venue, :extra)"
                ),
                rows,
            )


def _forget(conn: Connection, paper_ids: Iterable[str]) -> None:
    ids = list(paper_ids)
    for start in range(0, len(ids), _BATCH):
        batch = ids[start : start + _BATCH]
        marks = ", ".join(f":p{i}" for i in range(len(batch)))
        params = {f"p{i}": paper_id for i, paper_id in enumerate(batch)}
        conn.execute(text(f"DELETE FROM {TABLE} WHERE paper_id IN ({marks})"), params)


def _touched(objects: Iterable[object]) -> set[str]:
    found: set[str] = set()
    for item in objects:
        if isinstance(item, Paper):
            found.add(item.id)
        elif isinstance(item, PaperAuthor | PaperIdentifier):
            found.add(item.paper_id)
    return found


@event.listens_for(Session, "after_flush")
def _keep_in_step(session: Session, _: UOWTransaction) -> None:
    deleted = {item.id for item in session.deleted if isinstance(item, Paper)}
    changed = _touched([*session.new, *session.dirty, *session.deleted]) - deleted
    if not changed and not deleted:
        return
    conn = session.connection()
    if deleted:
        _forget(conn, deleted)
    if changed:
        reindex(conn, changed)


def ensure_complete(db: Database) -> bool:
    """Rebuild the index if it does not cover exactly the papers there are. True if rebuilt."""
    with db.engine.connect() as conn:
        papers = conn.execute(text("SELECT count(*) FROM paper")).scalar_one()
        indexed = conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one()
    if papers == indexed:
        return False
    started = time.perf_counter()
    with db.write_session() as session:
        conn = session.connection()
        conn.execute(text(f"DELETE FROM {TABLE}"))
        reindex(conn, session.scalars(text("SELECT id FROM paper")))
    logger.info(
        "search index rebuilt",
        extra={"papers": papers, "seconds": round(time.perf_counter() - started, 2)},
    )
    return True


@dataclass(frozen=True)
class Hits:
    paper_ids: list[str]
    elapsed_ms: float


def match_expression(query: str) -> str | None:
    """Every word must appear, as a word or the start of one ("revi" finds "review")."""
    words = _TOKEN.findall(fold(query))
    if not words:
        return None
    return " ".join(f'"{word}"*' for word in words)


def search(db: Database, query: str, *, limit: int = MAX_HITS) -> Hits:
    """Paper ids matching every word of `query`, best first (title and author hits weigh most)."""
    started = time.perf_counter()
    expression = match_expression(query)
    if expression is None:
        return Hits([], 0.0)
    with db.engine.connect() as conn:
        rows: Sequence[Any] = conn.execute(
            text(
                f"SELECT paper_id FROM {TABLE} WHERE {TABLE} MATCH :expression "
                f"ORDER BY bm25({TABLE}, {_WEIGHTS}) LIMIT :limit"
            ),
            {"expression": expression, "limit": limit},
        ).all()
    return Hits([row[0] for row in rows], (time.perf_counter() - started) * 1000)
