"""Task 15: BibTeX and RIS exports become `NormalizedRecord`s, and bad entries are reported.

The sample files in tests/fixtures/imports are written by hand in the shape IEEE Xplore and
Scopus export, with broken entries mixed in on purpose.
"""

from pathlib import Path

import pytest

from tez.core.errors import ErrorCode, TezError
from tez.modules.importers.bibtex import parse_bibtex
from tez.modules.importers.parsing import ImportFormat, IssueCode, RecordWarning
from tez.modules.importers.ris import parse_ris
from tez.modules.importers.service import decode_text, detect_format, parse_file
from tez.modules.library.models import IdentifierScheme, VenueType

FIXTURES = Path(__file__).parent.parent / "fixtures" / "imports"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- BibTeX ---------------------------------------------------------------------------


def test_an_ieee_bibtex_export_maps_to_records() -> None:
    parsed = parse_bibtex(fixture("ieee-xplore.bib"))

    first = parsed.entries[0]
    assert first.line == 1
    assert first.key == "10012345"
    assert first.warnings == ()
    record = first.record
    assert record.title == "Automated Code Review with Large Language Models: An Empirical Study"
    assert record.year == 2024
    assert record.venue == "IEEE Transactions on Software Engineering"
    assert record.venue_type is VenueType.JOURNAL
    assert (record.volume, record.issue, record.pages) == ("50", "3", "512-530")
    assert record.identifiers == {IdentifierScheme.DOI: "10.1109/TSE.2024.0012345"}


def test_latex_is_decoded_into_turkish_letters() -> None:
    record = parse_bibtex(fixture("ieee-xplore.bib")).entries[0].record

    names = [(a.given, a.family) for a in record.authors]
    assert names == [("Ayşe", "Yılmaz"), ("Mehmet", "Çelik"), ("Kees", "van der Berg")]
    assert record.abstract == "We study how LLMs review code in İstanbul and elsewhere."


def test_a_braced_corporate_author_stays_one_name() -> None:
    record = parse_bibtex(fixture("ieee-xplore.bib")).entries[1].record

    assert [a.display_name for a in record.authors] == [
        "IEEE Software Engineering Team",
        "Jane Doe",
    ]
    assert record.venue_type is VenueType.CONFERENCE


def test_an_arxiv_entry_is_a_preprint_with_its_id() -> None:
    record = parse_bibtex(fixture("ieee-xplore.bib")).entries[2].record

    assert record.title == "BERT-style Models for Code Review Comments"
    assert record.venue_type is VenueType.PREPRINT
    assert record.identifiers == {IdentifierScheme.ARXIV: "2401.01234"}


def test_broken_bibtex_entries_are_reported_and_the_rest_imported() -> None:
    parsed = parse_bibtex(fixture("ieee-xplore.bib"))

    assert [e.key for e in parsed.entries] == [
        "10012345",
        "9876543",
        "smith2024preprint",
        "lateyear",
    ]
    issues = [(i.code, i.key) for i in parsed.issues]
    assert issues == [
        (IssueCode.DUPLICATE_KEY, "10012345"),
        (IssueCode.NO_TITLE, "notitle2024"),
        (IssueCode.UNPARSEABLE, "broken2022"),
    ]
    assert all(i.line is not None for i in parsed.issues)
    assert parsed.total == 7


def test_an_unreadable_year_is_a_warning_not_a_lost_record() -> None:
    entry = parse_bibtex(fixture("ieee-xplore.bib")).entries[3]

    assert entry.record.year is None
    assert entry.warnings == (RecordWarning.BAD_YEAR,)
    assert entry.record.identifiers == {IdentifierScheme.ISBN: "978-3-16-148410-0"}


def test_an_empty_bibtex_file_has_nothing_and_no_issues() -> None:
    parsed = parse_bibtex("% just a comment\n")

    assert parsed.entries == []
    assert parsed.issues == []


# --- RIS ------------------------------------------------------------------------------


def test_a_scopus_ris_export_maps_to_records() -> None:
    parsed = parse_ris(fixture("scopus.ris"))

    record = parsed.entries[0].record
    assert parsed.entries[0].key == "scopus-1"
    assert record.title == "Automated code review with large language models: an empirical study"
    assert [(a.given, a.family) for a in record.authors] == [("A.", "Yılmaz"), ("M.", "Çelik")]
    assert record.year == 2024
    assert record.venue == "IEEE Transactions on Software Engineering"
    assert record.pages == "512-530"
    assert record.identifiers == {IdentifierScheme.DOI: "10.1109/tse.2024.0012345"}

    second = parsed.entries[1].record
    assert second.year == 2022  # from "2022///"
    assert second.venue_type is VenueType.CONFERENCE


def test_broken_ris_records_are_reported_with_their_lines() -> None:
    parsed = parse_ris(fixture("scopus.ris"))

    assert [(i.code, i.line) for i in parsed.issues] == [
        (IssueCode.NO_TITLE, 27),
        (IssueCode.TRUNCATED, 39),
    ]
    assert len(parsed.entries) == 3
    assert parsed.total == 5


def test_missing_fields_become_warnings() -> None:
    entry = parse_ris(fixture("scopus.ris")).entries[2]

    assert entry.record.title == "Code Review: A Handbook Chapter"
    assert entry.record.url is None
    assert entry.warnings == (
        RecordWarning.NO_AUTHORS,
        RecordWarning.NO_IDENTIFIER,
        RecordWarning.BAD_LINK,
    )


def test_text_before_the_first_record_is_reported_and_crlf_is_read() -> None:
    text = (
        "Exported from Scopus\r\n\r\n"
        "TY  - JOUR\r\nTI  - Windows Line Endings Work Too\r\nPY  - 2019\r\nER  - \r\n"
    )

    parsed = parse_ris(text)

    assert [e.record.title for e in parsed.entries] == ["Windows Line Endings Work Too"]
    assert [(i.code, i.line) for i in parsed.issues] == [(IssueCode.STRAY_TEXT, 1)]
    assert parsed.total == 1


# --- format and encoding --------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("refs.bib", "", ImportFormat.BIBTEX),
        ("refs.RIS", "", ImportFormat.RIS),
        ("export.txt", "TY  - JOUR\nER  - \n", ImportFormat.RIS),
        ("export.txt", "% header\n@article{a, title={x}}", ImportFormat.BIBTEX),
    ],
)
def test_the_format_comes_from_the_extension_or_the_content(
    name: str, text: str, expected: ImportFormat
) -> None:
    assert detect_format(name, text) is expected


def test_an_unknown_format_is_an_error() -> None:
    with pytest.raises(TezError) as caught:
        detect_format("notes.txt", "just some notes")

    assert caught.value.code is ErrorCode.IMPORT_UNKNOWN_FORMAT


def test_utf8_with_bom_and_windows_1252_are_both_read() -> None:
    assert decode_text("﻿TY  - JOUR".encode()) == "TY  - JOUR"
    assert decode_text("Müller".encode("cp1252")) == "Müller"


def test_a_windows_1252_bibtex_file_imports() -> None:
    data = "@article{k, title={Über Code Review}, author={Müller, Jörg}}".encode("cp1252")

    parsed, _ = parse_file("old.bib", data)

    assert parsed.entries[0].record.title == "Über Code Review"
    assert parsed.entries[0].record.authors[0].family == "Müller"
