"""Full-text search inside PDFs: the `chunk_fts` FTS5 table over `text_chunk` (Task 44).

Like `paper_fts` (ADR 0014), the indexed text is folded here, because FTS5's own tokenizer folds
Turkish wrongly. The table is contentless: it keeps the word index and not a second copy of every
page. `text_chunk.search_row` is its rowid, and a trigger removes a page from the index when its
row goes (migration 0020).
"""

import json
import logging
import re
import time
from collections.abc import Iterable, Sequence

from sqlalchemy import Connection, text

from tez.core.db import Database
from tez.modules.fulltext.extraction import SOFT_HYPHEN, readable
from tez.shared.text import fold
from tez.shared.textsearch import Segment, Term, expression, passage

logger = logging.getLogger(__name__)

TABLE = "chunk_fts"
_BATCH = 200
# Best pages looked at for one query; more than anyone reads, and it bounds the work.
MAX_PAGES = 2000
_BROKEN = re.compile(rf"(\w+){SOFT_HYPHEN}[ \t]*[\r\n]+[ \t]*(\w+)")


def index_text(page: str) -> str:
    """What is indexed for a page. A word broken over two lines is indexed joined and in halves:
    "cost-<line end>benefit" may be one word or two, and the PDF does not say which."""
    halves = " ".join(f"{first} {second}" for first, second in _BROKEN.findall(page))
    return fold(f"{readable(page)}\n{readable(halves)}")


def add(conn: Connection, rows: Iterable[tuple[int, str]]) -> None:
    """Index pages given as (search_row, page text)."""
    batch = [{"row": row, "text": index_text(page)} for row, page in rows]
    if batch:
        conn.execute(text(f"INSERT INTO {TABLE} (rowid, text) VALUES (:row, :text)"), batch)


def ensure_complete(db: Database) -> bool:
    """Rebuild the index if it does not cover exactly the pages there are. True if rebuilt."""
    with db.engine.connect() as conn:
        pages = conn.execute(text("SELECT count(*) FROM text_chunk")).scalar_one()
        indexed = conn.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one()
    if pages == indexed:
        return False
    started = time.perf_counter()
    with db.write_session() as session:
        conn = session.connection()
        conn.execute(text(f"INSERT INTO {TABLE} ({TABLE}) VALUES ('delete-all')"))
        last = 0
        while True:
            rows = conn.execute(
                text(
                    "SELECT search_row, text FROM text_chunk WHERE search_row > :last "
                    "ORDER BY search_row LIMIT :batch"
                ),
                {"last": last, "batch": _BATCH},
            ).all()
            if not rows:
                break
            add(conn, [(row[0], row[1]) for row in rows])
            last = rows[-1][0]
    logger.info(
        "full-text index rebuilt",
        extra={"pages": pages, "seconds": round(time.perf_counter() - started, 2)},
    )
    return True


def find_pages(
    conn: Connection, terms: Sequence[Term], paper_ids: Iterable[str]
) -> list[tuple[int, str, str, int]]:
    """(search_row, paper_id, attachment_id, page_index) in these papers, best page first."""
    rows = conn.execute(
        text(
            "SELECT c.search_row, a.paper_id, c.attachment_id, c.page_index "
            f"FROM {TABLE} JOIN text_chunk c ON c.search_row = {TABLE}.rowid "
            "JOIN attachment a ON a.id = c.attachment_id "
            f"WHERE {TABLE} MATCH :expression "
            "AND a.paper_id IN (SELECT value FROM json_each(:papers)) "
            f"ORDER BY bm25({TABLE}) LIMIT :limit"
        ),
        {
            "expression": expression(terms),
            "papers": json.dumps(list(paper_ids)),
            "limit": MAX_PAGES,
        },
    )
    return [(row[0], row[1], row[2], row[3]) for row in rows]


def snippet(page: str, terms: Sequence[Term]) -> list[Segment]:
    """The passage of a page around the first match. A page matched only by half of a word
    broken over two lines shows its beginning."""
    return passage(readable(page).replace("\n", " "), terms)
