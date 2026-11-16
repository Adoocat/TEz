"""Snowballing sources (Task 36): references and citing papers from OpenAlex and Semantic
Scholar, checked against recorded real responses. These tests never reach the network."""

import pytest

from tests.unit.providers.conftest import run_with_http
from tez.core.errors import ErrorCode
from tez.modules.library.models import IdentifierScheme
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.base import ProviderResult
from tez.modules.snowballing.sources import (
    Direction,
    OpenAlexCitations,
    Seed,
    SemanticScholarCitations,
)

# "Modern code review: a case study at Google" (ICSE-SEIP 2018), known to both sources.
DOI = "10.1145/3183519.3183525"
SEED = Seed("seed", {IdentifierScheme.DOI: DOI})
LIMIT = 5


def openalex(seed: Seed, direction: Direction) -> ProviderResult:
    return run_with_http(
        lambda http: OpenAlexCitations(http).citations(seed, direction, limit=LIMIT)
    )


def semantic_scholar(seed: Seed, direction: Direction) -> ProviderResult:
    return run_with_http(
        lambda http: SemanticScholarCitations(http).citations(seed, direction, limit=LIMIT)
    )


def assert_papers(result: ProviderResult) -> None:
    assert result.status is RunStatus.OK, result.error
    assert len(result.records) == LIMIT
    for record in result.records:
        assert record.title
        assert record.identifiers


@pytest.mark.vcr
def test_openalex_finds_a_seed_by_doi_and_follows_its_references() -> None:
    result = openalex(SEED, Direction.BACKWARD)

    assert_papers(result)
    assert result.translated_query.startswith("cited_by:W")
    assert all(IdentifierScheme.OPENALEX in r.identifiers for r in result.records)


@pytest.mark.vcr
def test_openalex_lists_the_papers_citing_a_seed() -> None:
    result = openalex(SEED, Direction.FORWARD)

    assert_papers(result)
    assert result.translated_query.startswith("cites:W")
    assert result.total_reported is not None and result.total_reported >= LIMIT


@pytest.mark.vcr
def test_semantic_scholar_follows_references_and_citations() -> None:
    backward = semantic_scholar(SEED, Direction.BACKWARD)
    forward = semantic_scholar(SEED, Direction.FORWARD)

    assert_papers(backward)
    assert_papers(forward)
    assert backward.translated_query == f"DOI:{DOI}/references"
    assert forward.translated_query == f"DOI:{DOI}/citations"


@pytest.mark.vcr
def test_an_unknown_doi_is_reported_not_raised() -> None:
    unknown = Seed("x", {IdentifierScheme.DOI: "10.5555/tez.does-not-exist.20261116"})

    result = openalex(unknown, Direction.BACKWARD)

    assert not result.records
    assert result.error is not None
    assert result.error.code is ErrorCode.SNOWBALL_SEED_NOT_FOUND


def test_a_seed_without_identifiers_is_skipped_without_a_request() -> None:
    bare = Seed("x", {})

    for result in (openalex(bare, Direction.FORWARD), semantic_scholar(bare, Direction.FORWARD)):
        assert result.error is not None
        assert result.error.code is ErrorCode.SNOWBALL_SEED_UNIDENTIFIED
