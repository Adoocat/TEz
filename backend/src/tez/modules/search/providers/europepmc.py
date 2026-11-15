"""Europe PMC REST search (https://europepmc.org/RestfulWebService), ADR 0021.

Checked on 2026-11-15 (the page itself refuses non-browser clients; the Europe PMC team's
answers on its web-services forum): free, no key; `pageSize` up to 1000; deep paging only with
`cursorMark` (`*`, then each answer's `nextCursorMark`); about 10 requests a second per IP,
429 above. `resultType=core` carries abstracts, full author data and publication types.

Europe PMC holds PubMed's records (source MED) and more (preprints PPR, agricultural AGR…), so
its results overlap PubMed's; deduplication merges them by PMID, PMCID or DOI.
"""

import re
from typing import Any, ClassVar

from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.providers.base import (
    OnWait,
    Page,
    PagedProvider,
    SearchRequest,
    as_dict,
    as_list,
)
from tez.modules.search.providers.query import to_europepmc
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.http import HttpClient, SourcePolicy
from tez.shared.text import strip_markup

API_HOST = "www.ebi.ac.uk"
_URL = f"https://{API_HOST}/europepmc/webservices/rest/search"
_RATE = 5.0  # half the stated limit: other users share the IP at labs and campuses
_EARLIEST_YEAR = 1800
_LATEST_YEAR = 3000
_PREPRINT_SOURCE = "PPR"
_RETRACTED = {"retracted publication"}
_VENUE_TYPES = {
    "preprint": VenueType.PREPRINT,
    "congress": VenueType.CONFERENCE,
    "technical report": VenueType.REPORT,
    "book": VenueType.BOOK,
    "book chapter": VenueType.CHAPTER,
    "thesis": VenueType.THESIS,
    "dissertation": VenueType.THESIS,
}
_SECTION = re.compile(r"<h4>(.*?)</h4>", re.IGNORECASE)


def europepmc_policy() -> SourcePolicy:
    return SourcePolicy(name=EuropePmcProvider.name, requests_per_second=_RATE)


def _clean(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(strip_markup(value).split()) or None


def _abstract(value: Any) -> str | None:
    """Section headings come as <h4>; keep them as labels: "Background: …"."""
    if not isinstance(value, str):
        return None
    return _clean(_SECTION.sub(lambda m: f" {m.group(1)}: ", value))


def _author(author: dict[str, Any]) -> RecordAuthor:
    collective = author.get("collectiveName")
    author_id = as_dict(author.get("authorId"))
    orcid = author_id.get("value") if author_id.get("type") == "ORCID" else None
    affiliations = as_list(
        as_dict(author.get("authorAffiliationDetailsList")).get("authorAffiliation")
    )
    return RecordAuthor(
        display_name=collective or author.get("fullName") or "",
        family=None if collective else author.get("lastName"),
        given=None if collective else author.get("firstName"),
        orcid=orcid,
        affiliation=as_dict(affiliations[0]).get("affiliation") if affiliations else None,
    )


def _types(result: dict[str, Any]) -> set[str]:
    return {str(t).lower() for t in as_list(as_dict(result.get("pubTypeList")).get("pubType"))}


def _venue_type(result: dict[str, Any], types: set[str]) -> VenueType:
    if result.get("source") == _PREPRINT_SOURCE:
        return VenueType.PREPRINT
    return next((v for kind, v in _VENUE_TYPES.items() if kind in types), VenueType.JOURNAL)


def _pdf(result: dict[str, Any]) -> str | None:
    links = as_list(as_dict(result.get("fullTextUrlList")).get("fullTextUrl"))
    return next(
        (
            as_dict(link).get("url")
            for link in links
            if as_dict(link).get("documentStyle") == "pdf"
            and as_dict(link).get("availabilityCode") == "OA"
        ),
        None,
    )


def map_result(result: dict[str, Any]) -> NormalizedRecord:
    journal_info = as_dict(result.get("journalInfo"))
    journal = as_dict(journal_info.get("journal"))
    types = _types(result)
    pmid = result.get("pmid")
    url = (
        f"https://europepmc.org/article/{result.get('source')}/{result.get('id')}"
        if result.get("source") and result.get("id")
        else None
    )
    return NormalizedRecord.model_validate(
        {
            "title": _clean(result.get("title")),
            "authors": tuple(
                _author(as_dict(a))
                for a in as_list(as_dict(result.get("authorList")).get("author"))
            ),
            "year": result.get("pubYear") or journal_info.get("yearOfPublication"),
            "identifiers": {
                IdentifierScheme.PMID: pmid,
                IdentifierScheme.PMCID: result.get("pmcid"),
                IdentifierScheme.DOI: result.get("doi"),
            },
            "abstract": _abstract(result.get("abstractText")),
            "venue": journal.get("title")
            or as_dict(result.get("bookOrReportDetails")).get("publisher"),
            "venue_type": _venue_type(result, types),
            "volume": journal_info.get("volume"),
            "issue": journal_info.get("issue"),
            "pages": result.get("pageInfo"),
            "language": result.get("language"),
            "url": url,
            "oa_url": _pdf(result),
            "citation_count": result.get("citedByCount"),
            "is_retracted": bool(types & _RETRACTED),
        }
    )


def query_with_years(request: SearchRequest, translated: str) -> str:
    if request.year_from is None and request.year_to is None:
        return translated
    start = request.year_from or _EARLIEST_YEAR
    end = request.year_to or _LATEST_YEAR
    return f"({translated}) AND PUB_YEAR:[{start} TO {end}]"


class EuropePmcProvider(PagedProvider):
    name: str = "europepmc"
    page_size: ClassVar[int] = 500

    def __init__(self, http: HttpClient, *, email: str | None = None) -> None:
        super().__init__(http, europepmc_policy())
        self._email = email

    def translate(self, request: SearchRequest) -> str:
        query = to_europepmc(request.query)
        return query_with_years(request, query) if query else query

    async def fetch_page(
        self,
        request: SearchRequest,
        translated: str,
        cursor: str | int | None,
        size: int,
        on_wait: OnWait | None,
    ) -> Page:
        params: dict[str, Any] = {
            "query": translated,
            "format": "json",
            "resultType": "core",
            "pageSize": size,
            "cursorMark": cursor or "*",
        }
        if self._email:
            params["email"] = self._email
        response = await self._http.get(self._policy, _URL, params=params, on_wait=on_wait)
        body = self.json_object(response)
        if "resultList" not in body:
            raise self.bad_response("no_result_list")
        results = as_list(as_dict(body.get("resultList")).get("result"))
        hits = body.get("hitCount")
        return Page(
            items=results,
            raw=response.text,
            total=int(hits) if isinstance(hits, int | str) and str(hits).isdigit() else None,
            next_cursor=body.get("nextCursorMark") if results else None,
        )

    def map_item(self, item: Any) -> NormalizedRecord:
        return map_result(as_dict(item))
