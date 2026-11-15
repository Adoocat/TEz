"""Europe PMC: mapping checked against recorded real responses and a hand-written result;
its PubMed records merge with PubMed's by PMID (Task 29)."""

from typing import Any

import pytest

from tests.unit.providers.conftest import run_with_http
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.dedup import PaperIndex, candidate_from
from tez.modules.search.models import MatchMethod, RunStatus
from tez.modules.search.providers.base import ProviderResult, SearchRequest
from tez.modules.search.providers.europepmc import (
    EuropePmcProvider,
    europepmc_policy,
    map_result,
)
from tez.modules.search.providers.query import to_europepmc
from tez.modules.search.schemas import NormalizedRecord


class SmallPages(EuropePmcProvider):
    page_size = 2


def search(
    request: SearchRequest, provider: type[EuropePmcProvider] = EuropePmcProvider
) -> ProviderResult:
    return run_with_http(lambda http: provider(http).search(request))


@pytest.mark.vcr
def test_search_maps_a_real_response() -> None:
    result = search(
        SearchRequest(
            '"Anxiety Disorders"[MeSH] AND adolescent NOT review',
            year_from=2020,
            year_to=2024,
            limit=3,
        )
    )

    assert result.status is RunStatus.OK
    assert result.translated_query == (
        '(MESH:"Anxiety Disorders" AND adolescent NOT review) AND PUB_YEAR:[2020 TO 2024]'
    )
    assert len(result.records) == 3
    assert result.total_reported is not None and result.total_reported >= 3
    for record in result.records:
        assert record.title
        assert record.identifiers
        assert record.year is not None and 2020 <= record.year <= 2024
        assert record.url and record.url.startswith("https://europepmc.org/article/")


@pytest.mark.vcr
def test_paging_follows_the_cursor() -> None:
    result = search(SearchRequest("depression adolescents", limit=3), SmallPages)

    assert len(result.records) == 3
    assert len(result.raw_pages) == 2
    assert len({r.title for r in result.records}) == 3


@pytest.mark.vcr
def test_a_query_with_no_hits_is_an_empty_run() -> None:
    result = search(SearchRequest('"zqxjvbnmtezyok" AND "kwpzrtyunfound"', limit=3))

    assert result.status is RunStatus.OK
    assert result.records == ()
    assert result.total_reported == 0


def test_the_rate_stays_under_the_stated_limit() -> None:
    assert europepmc_policy().requests_per_second == 5


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ('"code review" AND (LLM OR GPT) NOT survey', '"code review" AND (LLM OR GPT) NOT survey'),
        ('"Neoplasms"[MeSH] AND smoking', 'MESH:"Neoplasms" AND smoking'),
        ("asthma [tiab] OR yilmaz[au]", "TITLE_ABS:asthma OR AUTH:yilmaz"),
        ('"Anxiety"[MeSH Terms] NOT pain[sb]', 'MESH:"Anxiety" NOT pain'),
    ],
)
def test_query_translation(query: str, expected: str) -> None:
    assert to_europepmc(query) == expected


RESULT: dict[str, Any] = {
    "id": "38000001",
    "source": "MED",
    "pmid": "38000001",
    "pmcid": "PMC10700001",
    "doi": "10.5080/u27000",
    "title": "Ergenlerde <i>kaygı</i> bozuklukları.",
    "authorList": {
        "author": [
            {
                "fullName": "Yılmaz A",
                "firstName": "Ayşe",
                "lastName": "Yılmaz",
                "authorId": {"type": "ORCID", "value": "0000-0002-1825-0097"},
                "authorAffiliationDetailsList": {
                    "authorAffiliation": [{"affiliation": "Hacettepe Üniversitesi."}]
                },
            },
            {"collectiveName": "TEz Çalışma Grubu"},
        ]
    },
    "journalInfo": {
        "volume": "12",
        "issue": "3",
        "yearOfPublication": 2023,
        "journal": {"title": "Türk Psikiyatri Dergisi"},
    },
    "pubYear": "2023",
    "pageInfo": "201-209",
    "abstractText": "<h4>Amaç</h4>Kaygıyı incelemek.<h4>Yöntem</h4>Tarama.",
    "language": "tur",
    "pubTypeList": {"pubType": ["Journal Article", "Retracted Publication"]},
    "fullTextUrlList": {
        "fullTextUrl": [
            {"availabilityCode": "OA", "documentStyle": "html", "url": "https://x/h"},
            {"availabilityCode": "OA", "documentStyle": "pdf", "url": "https://x/p.pdf"},
        ]
    },
    "citedByCount": 4,
}


def test_a_result_is_mapped_field_by_field() -> None:
    record = map_result(RESULT)

    assert record.title == "Ergenlerde kaygı bozuklukları."
    assert record.year == 2023
    assert (record.venue, record.venue_type) == ("Türk Psikiyatri Dergisi", VenueType.JOURNAL)
    assert (record.volume, record.issue, record.pages) == ("12", "3", "201-209")
    assert record.abstract == "Amaç: Kaygıyı incelemek. Yöntem: Tarama."
    assert record.is_retracted is True
    assert record.oa_url == "https://x/p.pdf"
    assert record.citation_count == 4
    assert record.url == "https://europepmc.org/article/MED/38000001"
    assert record.identifiers == {
        IdentifierScheme.PMID: "38000001",
        IdentifierScheme.PMCID: "PMC10700001",
        IdentifierScheme.DOI: "10.5080/u27000",
    }
    first, group = record.authors
    assert (first.family, first.given, first.orcid) == ("Yılmaz", "Ayşe", "0000-0002-1825-0097")
    assert first.affiliation == "Hacettepe Üniversitesi."
    assert (group.display_name, group.family) == ("TEz Çalışma Grubu", None)


def test_a_preprint_is_a_preprint() -> None:
    record = map_result({"id": "PPR1", "source": "PPR", "title": "T", "pubYear": "2024"})
    assert record.venue_type is VenueType.PREPRINT


def test_its_pubmed_records_merge_with_pubmeds() -> None:
    from_pubmed = NormalizedRecord(
        title="Adolescent anxiety: a cohort", identifiers={IdentifierScheme.PMID: "38000001"}
    )
    index = PaperIndex([candidate_from("paper-1", from_pubmed)])

    match = index.match(map_result(RESULT))

    assert (match.method, match.paper_id) == (MatchMethod.ID, "paper-1")
