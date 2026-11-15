"""PubMed through NCBI E-utilities (https://www.ncbi.nlm.nih.gov/books/NBK25497/), ADR 0021.

Policy checked on 2026-11-15 (NLM support article KA-05510): up to 3 requests a second without
an API key; `tool` and `email` identify the client. Each page is two calls: ESearch for the
PMIDs (JSON), then EFetch for their records (PubMed XML). ESearch serves at most the first
10,000 PMIDs of a query, more than any one run here asks for.

ElementTree does not fetch external entities (EFetch's DOCTYPE names a DTD it does not load),
and the bundled expat limits entity expansion, so it is safe for this input.
"""

import re
import xml.etree.ElementTree as ET
from typing import Any, ClassVar

from tez.core.errors import ErrorCode, TezError
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.providers.base import (
    OnWait,
    Page,
    PagedProvider,
    SearchRequest,
    as_dict,
    as_list,
)
from tez.modules.search.providers.query import to_pubmed
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.http import HttpClient, SourcePolicy

API_HOST = "eutils.ncbi.nlm.nih.gov"
_BASE = f"https://{API_HOST}/entrez/eutils"
_TOOL = "TEz"
_RATE = 3.0
_MAX_START = 9_999  # ESearch: retstart beyond this is refused for PubMed.
_ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
_YEAR = re.compile(r"\b(1[89]\d\d|2\d\d\d)\b")
_RETRACTED = {"Retracted Publication"}
# PubMed publication types that say more than "Journal Article".
_VENUE_TYPES = {
    "Preprint": VenueType.PREPRINT,
    "Congress": VenueType.CONFERENCE,
    "Technical Report": VenueType.REPORT,
}


def pubmed_policy() -> SourcePolicy:
    return SourcePolicy(name=PubMedProvider.name, requests_per_second=_RATE)


def _text(element: ET.Element | None) -> str | None:
    """All the text of an element, inline markup (<i>, <sup>) included."""
    if element is None:
        return None
    text = " ".join("".join(element.itertext()).split())
    return text or None


def _author(element: ET.Element) -> RecordAuthor | None:
    collective = _text(element.find("CollectiveName"))
    family = _text(element.find("LastName"))
    given = _text(element.find("ForeName")) or _text(element.find("Initials"))
    name = collective or " ".join(part for part in (given, family) if part)
    if not name:
        return None
    orcid = next(
        (
            match.group(0)
            for ident in element.findall("Identifier")
            if ident.get("Source") == "ORCID" and (match := _ORCID.search(ident.text or ""))
        ),
        None,
    )
    return RecordAuthor(
        display_name=name,
        family=None if collective else family,
        given=None if collective else given,
        orcid=orcid,
        affiliation=_text(element.find("AffiliationInfo/Affiliation")),
    )


def _year(article: ET.Element) -> int | None:
    date = article.find("Journal/JournalIssue/PubDate")
    text = _text(date.find("Year")) if date is not None else None
    if text is None and date is not None:
        text = _text(date.find("MedlineDate"))  # "2023 Nov-Dec"
    match = _YEAR.search(text or "")
    return int(match.group(1)) if match else None


def _abstract(article: ET.Element) -> str | None:
    """Structured abstracts keep their section labels: "BACKGROUND: … METHODS: …"."""
    parts: list[str] = []
    for section in article.findall("Abstract/AbstractText"):
        text = _text(section)
        if text:
            label = section.get("Label")
            parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts) or None


def _ids(item: ET.Element) -> dict[IdentifierScheme, str | None]:
    found: dict[IdentifierScheme, str | None] = {
        IdentifierScheme.PMID: _text(item.find("MedlineCitation/PMID")),
    }
    for ident in item.findall("PubmedData/ArticleIdList/ArticleId"):
        kind = ident.get("IdType")
        if kind == "doi":
            found[IdentifierScheme.DOI] = _text(ident)
        elif kind == "pmc":
            found[IdentifierScheme.PMCID] = _text(ident)
    return found


def _venue_type(types: set[str]) -> VenueType:
    return next((v for kind, v in _VENUE_TYPES.items() if kind in types), VenueType.JOURNAL)


def map_article(item: ET.Element) -> NormalizedRecord:
    """One <PubmedArticle> as a record. Book records (<PubmedBookArticle>) are not mapped."""
    citation = item.find("MedlineCitation")
    article = citation.find("Article") if citation is not None else None
    if article is None:
        raise ValueError("not a PubmedArticle")
    authors = (_author(a) for a in article.findall("AuthorList/Author"))
    types = {_text(t) or "" for t in article.findall("PublicationTypeList/PublicationType")}
    issue = article.find("Journal/JournalIssue")
    ids = _ids(item)
    pmid = ids[IdentifierScheme.PMID]
    return NormalizedRecord.model_validate(
        {
            "title": _text(article.find("ArticleTitle")) or _text(article.find("VernacularTitle")),
            "authors": tuple(a for a in authors if a is not None),
            "year": _year(article),
            "identifiers": ids,
            "abstract": _abstract(article),
            "venue": _text(article.find("Journal/Title")),
            "venue_type": _venue_type(types),
            "volume": _text(issue.find("Volume")) if issue is not None else None,
            "issue": _text(issue.find("Issue")) if issue is not None else None,
            "pages": _text(article.find("Pagination/MedlinePgn")),
            "language": _text(article.find("Language")),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            "is_retracted": bool(types & _RETRACTED),
        }
    )


def _date_params(request: SearchRequest) -> dict[str, Any]:
    if request.year_from is None and request.year_to is None:
        return {}
    return {
        "datetype": "pdat",
        "mindate": str(request.year_from or 1800),
        "maxdate": str(request.year_to or 3000),
    }


class PubMedProvider(PagedProvider):
    name: str = "pubmed"
    page_size: ClassVar[int] = 200

    def __init__(self, http: HttpClient, *, email: str | None = None) -> None:
        super().__init__(http, pubmed_policy())
        self._email = email

    def translate(self, request: SearchRequest) -> str:
        return to_pubmed(request.query)

    def _identity(self) -> dict[str, str]:
        return {"tool": _TOOL, **({"email": self._email} if self._email else {})}

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        start = int(cursor or 0)
        search = await self._http.get(
            self._policy,
            f"{_BASE}/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": translated,
                "retstart": start,
                "retmax": size,
                "retmode": "json",
                "sort": "relevance",
                **_date_params(request),
                **self._identity(),
            },
            on_wait=on_wait,
        )
        result = as_dict(self.json_object(search).get("esearchresult"))
        if not result:
            raise self.bad_response("no_esearchresult")
        if "ERROR" in result:
            raise TezError(ErrorCode.SOURCE_REJECTED, {"source": self.name}, status=502)
        ids = [str(pmid) for pmid in as_list(result.get("idlist"))]
        count = int(str(result.get("count") or 0))
        if not ids:
            return Page(items=[], raw=search.text, total=count)
        fetched = await self._http.get(
            self._policy,
            f"{_BASE}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml", **self._identity()},
            on_wait=on_wait,
        )
        try:
            root = ET.fromstring(fetched.text)
        except ET.ParseError as exc:
            raise self.bad_response("not_xml") from exc
        # EFetch answers in no set order: keep ESearch's ranking.
        # Book records come too; they fail to map and are counted as skipped.
        by_pmid = {
            _text(item.find("MedlineCitation/PMID")) or _text(item.find("BookDocument/PMID")): item
            for item in root
        }
        following = start + len(ids)
        return Page(
            items=[by_pmid[pmid] for pmid in ids if pmid in by_pmid],
            raw=search.text + "\n" + fetched.text,
            total=count,
            next_cursor=following if following < min(count, _MAX_START) else None,
        )

    def map_item(self, item: Any) -> NormalizedRecord:
        return map_article(item)
