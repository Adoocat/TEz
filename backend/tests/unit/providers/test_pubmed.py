"""PubMed (E-utilities): mapping checked against recorded real responses and a hand-written
record; deduplication recognizes PMIDs and PMCIDs (Task 29)."""

import xml.etree.ElementTree as ET

import pytest

from tests.unit.providers.conftest import run_with_http
from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.dedup import PaperIndex, candidate_from
from tez.modules.search.models import MatchMethod, RunStatus
from tez.modules.search.providers.base import ProviderResult, SearchRequest
from tez.modules.search.providers.pubmed import PubMedProvider, map_article, pubmed_policy
from tez.modules.search.providers.query import to_pubmed
from tez.modules.search.schemas import NormalizedRecord
from tez.shared.identifiers import normalize_pmcid, normalize_pmid


class SmallPages(PubMedProvider):
    page_size = 2


def search(
    request: SearchRequest, provider: type[PubMedProvider] = PubMedProvider
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
    assert result.translated_query == '"Anxiety Disorders"[MeSH] AND adolescent NOT review'
    assert len(result.records) == 3
    assert result.total_reported is not None and result.total_reported >= 3
    for record in result.records:
        assert record.title
        assert record.identifiers[IdentifierScheme.PMID].isdigit()
        assert record.year is not None and 2020 <= record.year <= 2024
        assert record.venue
        assert record.url and record.url.startswith("https://pubmed.ncbi.nlm.nih.gov/")


@pytest.mark.vcr
def test_paging_moves_the_start() -> None:
    result = search(SearchRequest("depression adolescents", limit=3), SmallPages)

    assert len(result.records) == 3
    assert len(result.raw_pages) == 2
    assert len({r.identifiers[IdentifierScheme.PMID] for r in result.records}) == 3


@pytest.mark.vcr
def test_a_query_with_no_hits_is_an_empty_run() -> None:
    result = search(SearchRequest('"zqxjvbnmtezyok" AND "kwpzrtyunfound"', limit=3))

    assert result.status is RunStatus.OK
    assert result.records == ()
    assert result.total_reported == 0


def test_the_rate_is_ncbis_keyless_limit() -> None:
    assert pubmed_policy().requests_per_second == 3


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ('"code review" AND (LLM OR GPT) NOT survey', '"code review" AND (LLM OR GPT) NOT survey'),
        ('"Neoplasms"[MeSH] AND smoking', '"Neoplasms"[MeSH] AND smoking'),
        ("asthma[tiab] OR wheeze [tiab]", "asthma[tiab] OR wheeze[tiab]"),
        ('"Anxiety"[MeSH Terms] NOT review', '"Anxiety"[MeSH Terms] NOT review'),
        ("((stress)", "(stress)"),
    ],
)
def test_query_translation(query: str, expected: str) -> None:
    assert to_pubmed(query) == expected


ARTICLE = """
<PubmedArticle>
  <MedlineCitation Status="MEDLINE" Owner="NLM">
    <PMID Version="1">38000001</PMID>
    <Article PubModel="Print-Electronic">
      <Journal>
        <JournalIssue CitedMedium="Internet">
          <Volume>12</Volume><Issue>3</Issue>
          <PubDate><MedlineDate>2023 Nov-Dec</MedlineDate></PubDate>
        </JournalIssue>
        <Title>Türk Psikiyatri Dergisi</Title>
      </Journal>
      <ArticleTitle>Ergenlerde <i>kaygı</i> bozuklukları: bir tarama</ArticleTitle>
      <Pagination><MedlinePgn>201-9</MedlinePgn></Pagination>
      <Abstract>
        <AbstractText Label="AMAÇ">Kaygıyı incelemek.</AbstractText>
        <AbstractText Label="YÖNTEM">Tarama.</AbstractText>
      </Abstract>
      <AuthorList CompleteYN="Y">
        <Author ValidYN="Y">
          <LastName>Yılmaz</LastName><ForeName>Ayşe</ForeName><Initials>A</Initials>
          <Identifier Source="ORCID">https://orcid.org/0000-0002-1825-0097</Identifier>
          <AffiliationInfo>
            <Affiliation>Hacettepe Üniversitesi, Ankara.</Affiliation>
          </AffiliationInfo>
        </Author>
        <Author ValidYN="Y"><CollectiveName>TEz Çalışma Grubu</CollectiveName></Author>
      </AuthorList>
      <Language>tur</Language>
      <PublicationTypeList>
        <PublicationType UI="D016428">Journal Article</PublicationType>
        <PublicationType UI="D016441">Retracted Publication</PublicationType>
      </PublicationTypeList>
    </Article>
  </MedlineCitation>
  <PubmedData>
    <ArticleIdList>
      <ArticleId IdType="pubmed">38000001</ArticleId>
      <ArticleId IdType="doi">10.5080/u27000</ArticleId>
      <ArticleId IdType="pmc">PMC10700001</ArticleId>
    </ArticleIdList>
  </PubmedData>
</PubmedArticle>
"""


def test_a_record_is_mapped_field_by_field() -> None:
    record = map_article(ET.fromstring(ARTICLE))

    assert record.title == "Ergenlerde kaygı bozuklukları: bir tarama"
    assert record.year == 2023
    assert record.venue == "Türk Psikiyatri Dergisi"
    assert record.venue_type is VenueType.JOURNAL
    assert (record.volume, record.issue, record.pages) == ("12", "3", "201-9")
    assert record.abstract == "AMAÇ: Kaygıyı incelemek. YÖNTEM: Tarama."
    assert record.language == "tur"
    assert record.is_retracted is True
    assert record.identifiers == {
        IdentifierScheme.PMID: "38000001",
        IdentifierScheme.DOI: "10.5080/u27000",
        IdentifierScheme.PMCID: "PMC10700001",
    }
    first, group = record.authors
    assert (first.family, first.given, first.orcid) == ("Yılmaz", "Ayşe", "0000-0002-1825-0097")
    assert first.affiliation == "Hacettepe Üniversitesi, Ankara."
    assert (group.display_name, group.family) == ("TEz Çalışma Grubu", None)


def test_a_book_record_is_not_mapped() -> None:
    with pytest.raises(ValueError):
        map_article(ET.fromstring("<PubmedBookArticle><BookDocument/></PubmedBookArticle>"))


@pytest.mark.parametrize(
    ("value", "pmid", "pmcid"),
    [
        ("38000001", "38000001", "PMC38000001"),
        ("PMID: 38000001", "38000001", None),
        ("pmc10700001", None, "PMC10700001"),
        ("PMC10700001", None, "PMC10700001"),
        ("10.1/x", None, None),
    ],
)
def test_pubmed_identifiers_are_normalized(value: str, pmid: str | None, pmcid: str | None) -> None:
    assert normalize_pmid(value) == pmid
    assert normalize_pmcid(value) == pmcid


def _record(title: str, **ids: str) -> NormalizedRecord:
    return NormalizedRecord(
        title=title, identifiers={IdentifierScheme(scheme): v for scheme, v in ids.items()}
    )


@pytest.mark.parametrize(
    "incoming",
    [
        _record("A different title entirely", pmid="38000001"),
        _record("Another different title", pmcid="pmc10700001"),
    ],
)
def test_deduplication_knows_pmids_and_pmcids(incoming: NormalizedRecord) -> None:
    known = _record("Ergenlerde kaygı", pmid="PMID: 38000001", pmcid="PMC10700001")
    pool = PaperIndex([candidate_from("paper-1", known)])

    match = pool.match(incoming)

    assert (match.method, match.paper_id) == (MatchMethod.ID, "paper-1")
