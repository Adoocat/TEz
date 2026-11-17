"""Find the papers of a decision file in this library's review (plan, Task 41).

Matching reuses the search deduplication rules (Task 12) through the search service: an identifier
decides first, then a fuzzy title checked against year and first author. A wrong match would put a
colleague's decision on the wrong paper, so the same cautious thresholds apply.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from tez.core.db import Database
from tez.modules.dual_screening.fileformat import FileRecord
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.reviews import service as reviews
from tez.modules.search.models import MatchMethod
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.modules.search.service import preview_matches

_SCHEMES = {scheme.value: scheme for scheme in IdentifierScheme}
_VENUE_TYPES = {venue_type.value: venue_type for venue_type in VenueType}


class MatchProblem(StrEnum):
    # No paper of this library is the record.
    NOT_FOUND = "not_found"
    # The paper is in this library but was never taken into the review.
    NOT_IN_REVIEW = "not_in_review"
    # An earlier record of the file already matched the same paper.
    DUPLICATE = "duplicate"


@dataclass(frozen=True)
class RecordMatch:
    ref: str
    paper_id: str | None
    method: MatchMethod
    problem: MatchProblem | None = None


def normalized(record: FileRecord) -> NormalizedRecord:
    """The record as search deduplication reads it. Unknown schemes and types are left out."""
    author = record.first_author
    return NormalizedRecord(
        title=record.title,
        authors=(RecordAuthor(display_name=author.display_name, family=author.family),)
        if author
        else (),
        year=record.year,
        identifiers={
            _SCHEMES[scheme]: value
            for scheme, value in record.identifiers.items()
            if scheme in _SCHEMES and value.strip()
        },
        venue_type=_VENUE_TYPES.get(record.venue_type or ""),
    )


def match_records(db: Database, review_id: str, records: Sequence[FileRecord]) -> list[RecordMatch]:
    """One result per record, in file order. Each paper is matched by at most one record."""
    found = preview_matches(db, [normalized(record) for record in records])
    in_review = reviews.paper_ids_in_review(db, review_id)
    taken: set[str] = set()
    matches: list[RecordMatch] = []
    for record, match in zip(records, found, strict=True):
        paper_id = match.paper_id
        if paper_id is None:
            matches.append(RecordMatch(record.ref, None, match.method, MatchProblem.NOT_FOUND))
        elif paper_id not in in_review:
            matches.append(RecordMatch(record.ref, None, match.method, MatchProblem.NOT_IN_REVIEW))
        elif paper_id in taken:
            matches.append(RecordMatch(record.ref, None, match.method, MatchProblem.DUPLICATE))
        else:
            taken.add(paper_id)
            matches.append(RecordMatch(record.ref, paper_id, match.method))
    return matches
