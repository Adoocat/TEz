"""Is this record a paper we already know? (plan, Task 12)

Identifiers decide first: a shared DOI or source id is the same paper, whatever the titles say.
Then titles decide, with three checks against false merges: the years are within one of each
other, the first authors agree, and neither paper has an identifier that contradicts the other.

A preprint and its published version are separate papers linked by a relation (plan, "Sürüm
ilişkisi"), so a title match between them answers "new, version of that one".

A wrong merge is worse than a missed one. A missed duplicate is one more row to screen, but a
wrong merge loses a paper from a systematic review. The thresholds lean that way.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from tez.modules.library.models import IdentifierScheme as Scheme
from tez.modules.library.models import VenueType
from tez.modules.search.models import MatchMethod
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.identifiers import (
    normalize_arxiv,
    normalize_doi,
    normalize_isbn,
    normalize_pmcid,
    normalize_pmid,
)
from tez.shared.text import fold

# Below this, titles are not the same paper; rapidfuzz scores are 0 to 100.
_TITLE_THRESHOLD = 93.0
# With no author or year to check against, only a practically identical title will do.
_NEAR_EXACT_THRESHOLD = 99.0
_AUTHOR_THRESHOLD = 85.0
_MIN_TITLE_WORDS = 3
_YEAR_TOLERANCE = 1
_ARXIV_DOI_PREFIX = "10.48550/arxiv."
_PUBLISHED_TYPES = frozenset(set(VenueType) - {VenueType.PREPRINT, VenueType.OTHER})
# Digits and Roman numerals: "Part 1" and "Part 2" differ by one letter but are two papers.
_NUMERAL = re.compile(r"\d+|[ivxlc]+")
_ID_SCHEMES = (
    Scheme.ARXIV,
    Scheme.PMID,
    Scheme.PMCID,
    Scheme.S2,
    Scheme.OPENALEX,
    Scheme.DBLP,
    Scheme.ISBN,
    Scheme.ZOTERO,
)


@dataclass(frozen=True)
class Candidate:
    """What matching needs to know about a known paper. Built from a record or stored columns."""

    paper_id: str
    identifiers: Mapping[Scheme, str]
    title_norm: str
    year: int | None
    first_author: str | None
    is_preprint: bool


@dataclass(frozen=True)
class Match:
    method: MatchMethod
    paper_id: str | None = None
    score: float | None = None
    # Set on NEW: this record is another version of that paper.
    version_of: str | None = None


def normalize_identifier(scheme: Scheme, value: str) -> str | None:
    match scheme:
        case Scheme.DOI:
            return normalize_doi(value)
        case Scheme.ARXIV:
            return normalize_arxiv(value)
        case Scheme.ISBN:
            return normalize_isbn(value)
        case Scheme.PMID:
            return normalize_pmid(value)
        case Scheme.PMCID:
            return normalize_pmcid(value)
        case _:
            return value.strip() or None


def normalized_identifiers(record: NormalizedRecord) -> dict[Scheme, str]:
    """A record's usable identifiers in canonical form; an arXiv DOI also gives the arXiv id."""
    identifiers: dict[Scheme, str] = {}
    for scheme, value in record.identifiers.items():
        if (normalized := normalize_identifier(scheme, value)) is not None:
            identifiers[scheme] = normalized
    doi = identifiers.get(Scheme.DOI, "")
    if doi.startswith(_ARXIV_DOI_PREFIX):
        arxiv = normalize_arxiv(doi)
        if arxiv is not None:
            identifiers.setdefault(Scheme.ARXIV, arxiv)
    return identifiers


def family_name(author: RecordAuthor) -> str | None:
    """The folded last word of the family name: initials and word order vary between sources."""
    name = author.family or author.display_name
    if author.family is None and "," in name:
        name = name.split(",", 1)[0]
    words = fold(name).split()
    return words[-1].strip(".") if words else None


def is_preprint_type(venue_type: VenueType | None, identifiers: Mapping[Scheme, str]) -> bool:
    if venue_type is VenueType.PREPRINT:
        return True
    if venue_type in _PUBLISHED_TYPES or Scheme.ARXIV not in identifiers:
        return False
    doi = identifiers.get(Scheme.DOI)
    return doi is None or doi.startswith(_ARXIV_DOI_PREFIX)


def candidate_from(paper_id: str, record: NormalizedRecord) -> Candidate:
    identifiers = normalized_identifiers(record)
    return Candidate(
        paper_id=paper_id,
        identifiers=identifiers,
        title_norm=record.title_norm,
        year=record.year,
        first_author=family_name(record.authors[0]) if record.authors else None,
        is_preprint=is_preprint_type(record.venue_type, identifiers),
    )


def _numerals(title_norm: str) -> list[str]:
    return [word for word in title_norm.split() if _NUMERAL.fullmatch(word)]


def _year_buckets(year: int | None) -> Iterable[int | None]:
    if year is None:
        return ()
    return range(year - _YEAR_TOLERANCE, year + _YEAR_TOLERANCE + 1)


class PaperIndex:
    """The known papers, indexed for matching. Add papers as a search creates them."""

    def __init__(self, candidates: Iterable[Candidate]) -> None:
        self._by_paper: dict[str, Candidate] = {}
        self._by_identifier: dict[tuple[Scheme, str], Candidate] = {}
        self._by_year: defaultdict[int | None, list[Candidate]] = defaultdict(list)
        self.reload(candidates)

    def reload(self, candidates: Iterable[Candidate]) -> None:
        self._by_paper.clear()
        self._by_identifier.clear()
        self._by_year.clear()
        for candidate in candidates:
            self.add(candidate)

    def add(self, candidate: Candidate) -> None:
        self._by_paper[candidate.paper_id] = candidate
        for scheme, value in candidate.identifiers.items():
            self._by_identifier.setdefault((scheme, value), candidate)
        self._by_year[candidate.year].append(candidate)

    def knows(self, scheme: Scheme, value: str) -> bool:
        return (scheme, value) in self._by_identifier

    def add_identifiers(self, paper_id: str, identifiers: Mapping[Scheme, str]) -> None:
        """Identifiers a known paper just gained from another source."""
        candidate = self._by_paper[paper_id]
        for scheme, value in identifiers.items():
            self._by_identifier.setdefault((scheme, value), candidate)

    def match(self, record: NormalizedRecord) -> Match:
        incoming = candidate_from("", record)
        return self._by_identifiers(incoming) or self._by_title(incoming) or Match(MatchMethod.NEW)

    def _by_identifiers(self, incoming: Candidate) -> Match | None:
        doi = incoming.identifiers.get(Scheme.DOI)
        if doi is not None and (found := self._by_identifier.get((Scheme.DOI, doi))):
            return Match(MatchMethod.DOI, found.paper_id, 1.0)
        for scheme in _ID_SCHEMES:
            value = incoming.identifiers.get(scheme)
            if value is not None and (found := self._by_identifier.get((scheme, value))):
                return Match(MatchMethod.ID, found.paper_id, 1.0)
        return None

    def _pool(self, incoming: Candidate) -> list[Candidate]:
        if incoming.year is None:
            return [c for bucket in self._by_year.values() for c in bucket]
        pool = list(self._by_year[None])
        for year in _year_buckets(incoming.year):
            pool.extend(self._by_year.get(year, ()))
        return pool

    def _by_title(self, incoming: Candidate) -> Match | None:
        if len(incoming.title_norm.split()) < _MIN_TITLE_WORDS:
            return None
        pool = self._pool(incoming)
        found = process.extract(
            incoming.title_norm,
            [c.title_norm for c in pool],
            scorer=fuzz.ratio,
            score_cutoff=_TITLE_THRESHOLD,
            limit=10,
        )
        version: Candidate | None = None
        for _, score, position in found:  # Best score first.
            candidate = pool[position]
            if not _same_work(incoming, candidate, score):
                continue
            if incoming.is_preprint != candidate.is_preprint:
                version = version or candidate
                continue
            if _identifiers_conflict(incoming, candidate):
                continue
            return Match(MatchMethod.TITLE_FUZZY, candidate.paper_id, score / 100)
        return Match(MatchMethod.NEW, version_of=version.paper_id) if version else None


def _same_work(incoming: Candidate, known: Candidate, score: float) -> bool:
    """Whether two similar titles describe one work, in any version."""
    if _numerals(incoming.title_norm) != _numerals(known.title_norm):
        return False
    if incoming.first_author and known.first_author:
        author_score = fuzz.ratio(incoming.first_author, known.first_author)
        if author_score < _AUTHOR_THRESHOLD:
            return False
    elif score < _NEAR_EXACT_THRESHOLD:
        return False
    if incoming.year is None or known.year is None:
        return score >= _NEAR_EXACT_THRESHOLD
    return True


def _identifiers_conflict(incoming: Candidate, known: Candidate) -> bool:
    """Two different DOIs (or arXiv ids) mean two registered works, however alike the titles."""
    for scheme in (Scheme.DOI, Scheme.ARXIV):
        ours, theirs = incoming.identifiers.get(scheme), known.identifiers.get(scheme)
        if ours is not None and theirs is not None and ours != theirs:
            return True
    return False
