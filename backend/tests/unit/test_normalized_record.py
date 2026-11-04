"""`NormalizedRecord`: what every source and importer hands to deduplication."""

from typing import Any

import pytest
from pydantic import ValidationError

from tez.modules.library.models import IdentifierScheme, VenueType
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor


def test_a_title_alone_is_a_valid_record() -> None:
    record = NormalizedRecord(title="Attention Is All You Need")

    assert record.authors == ()
    assert record.identifiers == {}
    assert record.year is None
    assert record.abstract is None
    assert record.oa_url is None
    assert record.is_retracted is False


def test_all_fields_round_trip_through_json() -> None:
    record = NormalizedRecord(
        title="Automated Code Review with LLMs",
        authors=(
            RecordAuthor(
                display_name="Ayşe Yılmaz",
                family="Yılmaz",
                given="Ayşe",
                orcid="0000-0002-1825-0097",
                affiliation="ODTÜ",
            ),
        ),
        year=2024,
        identifiers={IdentifierScheme.DOI: "10.1145/3597503.3639187"},
        abstract="We study…",
        venue="ICSE",
        venue_type=VenueType.CONFERENCE,
        volume="1",
        issue="2",
        pages="1-12",
        language="en",
        url="https://example.org/paper",
        oa_url="https://example.org/paper.pdf",
        citation_count=12,
        is_retracted=True,
    )

    assert NormalizedRecord.model_validate_json(record.model_dump_json()) == record


def test_records_cannot_be_changed() -> None:
    record = NormalizedRecord(title="x")

    with pytest.raises(ValidationError):
        record.title = "y"  # pyright: ignore[reportAttributeAccessIssue]


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedRecord.model_validate({"title": "x", "titel": "y"})


# --- title ----------------------------------------------------------------------------


@pytest.mark.parametrize("title", ["", "   ", "\n\t"])
def test_a_record_without_a_title_is_rejected(title: str) -> None:
    with pytest.raises(ValidationError):
        NormalizedRecord(title=title)


def test_title_whitespace_is_collapsed() -> None:
    assert NormalizedRecord(title="  Deep\n   Learning\t ").title == "Deep Learning"


def test_title_norm_folds_turkish_letters() -> None:
    upper = NormalizedRecord(title="KOD İNCELEMEDE IŞIK: Bir Çalışma!")
    lower = NormalizedRecord(title="kod incelemede ışık — bir çalışma")

    assert upper.title_norm == lower.title_norm == "kod incelemede isik bir calisma"


# --- sources send messy data: bad optional values become "unknown", they do not fail ---


@pytest.mark.parametrize("year", [0, -5, 999, 3000])
def test_an_impossible_year_becomes_unknown(year: int) -> None:
    assert NormalizedRecord(title="x", year=year).year is None


@pytest.mark.parametrize("year", [1500, 1999, 2026])
def test_a_plausible_year_is_kept(year: int) -> None:
    assert NormalizedRecord(title="x", year=year).year == year


def test_a_negative_citation_count_becomes_unknown() -> None:
    assert NormalizedRecord(title="x", citation_count=-1).citation_count is None


@pytest.mark.parametrize(
    "field", ["abstract", "venue", "volume", "issue", "pages", "language", "url", "oa_url"]
)
def test_blank_text_becomes_none(field: str) -> None:
    fields: dict[str, Any] = {"title": "x", field: "  "}

    assert getattr(NormalizedRecord.model_validate(fields), field) is None


@pytest.mark.parametrize("field", ["volume", "issue", "pages"])
def test_overlong_short_fields_become_unknown(field: str) -> None:
    fields: dict[str, Any] = {"title": "x", field: "1" * 33}

    assert getattr(NormalizedRecord.model_validate(fields), field) is None


@pytest.mark.parametrize("field", ["url", "oa_url"])
@pytest.mark.parametrize("value", ["javascript:alert(1)", "ftp://example.org/x", "not a url"])
def test_only_web_links_are_kept(field: str, value: str) -> None:
    fields: dict[str, Any] = {"title": "x", field: value}

    assert getattr(NormalizedRecord.model_validate(fields), field) is None


def test_language_is_lower_case() -> None:
    assert NormalizedRecord(title="x", language="EN").language == "en"


# --- authors ---------------------------------------------------------------------------


def test_author_order_is_kept() -> None:
    names = ["Zeynep", "Ali", "Mehmet"]
    record = NormalizedRecord(title="x", authors=tuple(RecordAuthor(display_name=n) for n in names))

    assert [a.display_name for a in record.authors] == names


def test_authors_without_a_name_are_dropped() -> None:
    record = NormalizedRecord.model_validate(
        {"title": "x", "authors": [{"display_name": " "}, {"display_name": "Ali Veli"}]}
    )

    assert [a.display_name for a in record.authors] == ["Ali Veli"]


@pytest.mark.parametrize(
    "orcid",
    [
        "0000-0002-1825-0097",
        "https://orcid.org/0000-0002-1825-0097",
        "http://orcid.org/0000-0002-1825-0097",
        " 0000-0002-1825-0097 ",
    ],
)
def test_orcid_is_reduced_to_the_bare_identifier(orcid: str) -> None:
    author = RecordAuthor(display_name="A", orcid=orcid)

    assert author.orcid == "0000-0002-1825-0097"


def test_orcid_may_end_in_x() -> None:
    assert RecordAuthor(display_name="A", orcid="0000-0002-1694-233X").orcid == (
        "0000-0002-1694-233X"
    )


@pytest.mark.parametrize("orcid", ["", "abc", "0000-0002-1825", "https://example.org/0000"])
def test_an_unusable_orcid_becomes_none(orcid: str) -> None:
    assert RecordAuthor(display_name="A", orcid=orcid).orcid is None


# --- identifiers -----------------------------------------------------------------------


def test_identifiers_are_keyed_by_scheme() -> None:
    record = NormalizedRecord.model_validate(
        {"title": "x", "identifiers": {"doi": "10.1/abc", "arxiv": "2401.00001"}}
    )

    assert record.identifiers == {
        IdentifierScheme.DOI: "10.1/abc",
        IdentifierScheme.ARXIV: "2401.00001",
    }


def test_blank_and_missing_identifiers_are_dropped() -> None:
    record = NormalizedRecord.model_validate(
        {"title": "x", "identifiers": {"doi": "  ", "arxiv": None, "s2": " abc "}}
    )

    assert record.identifiers == {IdentifierScheme.S2: "abc"}


def test_an_unknown_identifier_scheme_is_a_bug_and_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedRecord.model_validate({"title": "x", "identifiers": {"issn": "1234"}})


def test_an_unknown_venue_type_is_a_bug_and_is_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedRecord.model_validate({"title": "x", "venue_type": "blog"})
