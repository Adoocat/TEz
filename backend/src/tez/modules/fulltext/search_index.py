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
from dataclasses import dataclass

from sqlalchemy import Connection, text

from tez.core.db import Database
from tez.modules.fulltext.extraction import SOFT_HYPHEN, readable
from tez.shared.text import fold, fold_with_map

logger = logging.getLogger(__name__)

TABLE = "chunk_fts"
_BATCH = 200
# Best pages looked at for one query; more than anyone reads, and it bounds the work.
MAX_PAGES = 2000
# Characters shown either side of the first match.
_CONTEXT = 110

_QUERY_PART = re.compile(r'"([^"]*)"|(\S+)')
_WORD = re.compile(r"\w+")
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


@dataclass(frozen=True)
class Term:
    """A folded word (or its beginning), or the words of a quoted phrase."""

    words: tuple[str, ...]
    phrase: bool


def parse(query: str) -> list[Term]:
    """Every term must appear on the page. Words match by their beginning ("revi" finds
    "review"); a quoted phrase matches exactly, word by word."""
    terms: list[Term] = []
    for quoted, plain in _QUERY_PART.findall(query):
        words = _WORD.findall(fold(quoted or plain))
        if quoted and words:
            terms.append(Term(tuple(words), phrase=True))
        else:
            # "peer-review" is two words; an unclosed quote is just a word.
            terms.extend(Term((word,), phrase=False) for word in words)
    return terms


def expression(terms: Sequence[Term]) -> str:
    parts: list[str] = []
    for term in terms:
        joined = " ".join(term.words)
        parts.append(f'"{joined}"' if term.phrase else f'"{joined}"*')
    return " ".join(parts)


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


@dataclass(frozen=True)
class Segment:
    text: str
    hit: bool


def _pattern(terms: Sequence[Term]) -> re.Pattern[str]:
    """Where the terms are in folded text."""
    parts: list[str] = []
    for term in terms:
        words = r"\W+".join(re.escape(word) for word in term.words)
        parts.append(rf"\b{words}\b" if term.phrase else rf"\b{words}\w*")
    return re.compile("|".join(parts))


def snippet(page: str, terms: Sequence[Term]) -> list[Segment]:
    """The passage around the first match, cut at word boundaries, with every match marked."""
    shown = readable(page).replace("\n", " ")
    folded = fold(shown)
    # Nearly every page folds one to one (`readable` already spelled ligatures out).
    origin: Sequence[int] = range(len(shown))
    if len(folded) != len(shown):
        folded, origin = fold_with_map(shown)
    found = [match.span() for match in _pattern(terms).finditer(folded)]
    if not found:
        # Matched only as half of a broken word: show the beginning of the page.
        end = _word_edge(shown, 2 * _CONTEXT, 1)
        return [Segment(shown[:end].strip() + ("…" if end < len(shown) else ""), hit=False)]
    spans = [(origin[start], origin[end - 1] + 1) for start, end in found]
    first = spans[0]
    start = _word_edge(shown, first[0] - _CONTEXT, -1)
    end = _word_edge(shown, first[1] + _CONTEXT, 1)
    segments: list[Segment] = []
    at = start
    for left, right in spans:
        if left < at or right > end:
            continue
        if left > at:
            segments.append(Segment(shown[at:left], hit=False))
        segments.append(Segment(shown[left:right], hit=True))
        at = right
    if at < end:
        segments.append(Segment(shown[at:end], hit=False))
    if start > 0:
        segments.insert(0, Segment("…", hit=False))
    if end < len(shown):
        segments.append(Segment("…", hit=False))
    return segments


def _word_edge(shown: str, at: int, direction: int) -> int:
    """The nearest space at or beyond `at`, so no word is cut in half."""
    at = max(0, min(at, len(shown)))
    while 0 < at < len(shown) and not shown[at - 1].isspace():
        at += direction
    return at
