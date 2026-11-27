"""Reading GROBID's TEI: the paper's sections and its reference list (Task 56).

Sections are the body's top-level `div`s with a heading; their type is guessed from the
heading in Turkish and English, and their pages come from the heading's coordinates. A
reference keeps what GROBID read (title, authors, year, DOI) and the raw text it read it from.
"""

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree

from tez.shared.text import fold

NS = {"tei": "http://www.tei-c.org/ns/1.0"}

# Heading words, folded, by section type. "other" when none matches.
_TYPES: list[tuple[str, tuple[str, ...]]] = [
    ("abstract", ("abstract", "ozet")),
    ("intro", ("introduction", "giris", "background", "arka plan")),
    (
        "method",
        ("method", "materials", "yontem", "metot", "gerec", "study design", "arastirma deseni"),
    ),
    ("results", ("result", "finding", "bulgu", "sonuclar")),
    ("discussion", ("discussion", "conclusion", "tartisma", "sonuc", "limitation", "sinirlilik")),
]
_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


@dataclass(frozen=True)
class Section:
    type: str
    heading: str
    page_start: int | None
    page_end: int | None


@dataclass(frozen=True)
class Reference:
    raw_text: str
    title: str | None
    authors: list[str] = field(default_factory=list[str])
    year: int | None = None
    doi: str | None = None
    page: int | None = None


@dataclass(frozen=True)
class Structure:
    sections: list[Section]
    references: list[Reference]


def section_type(heading: str) -> str:
    folded = fold(heading)
    folded = re.sub(r"^[\d.\s]+", "", folded)
    for kind, words in _TYPES:
        if any(word in folded for word in words):
            return kind
    return "other"


def _text(element: ElementTree.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _page(element: ElementTree.Element | None) -> int | None:
    """The first page of GROBID's coordinates: "page,x,y,w,h;page,...", pages from 1."""
    coords = element.get("coords") if element is not None else None
    if not coords:
        return None
    first = coords.split(";", 1)[0].split(",", 1)[0]
    return int(first) if first.isdigit() else None


def parse(tei: str) -> Structure:
    try:
        root = ElementTree.fromstring(tei)
    except ElementTree.ParseError as error:
        raise ValueError("not TEI XML") from error
    headed: list[tuple[str, int | None]] = []
    abstract = root.find(".//tei:profileDesc/tei:abstract", NS)
    if abstract is not None and _text(abstract):
        headed.append(("Abstract", 1))
    for div in root.findall(".//tei:text/tei:body/tei:div", NS):
        head = div.find("tei:head", NS)
        heading = _text(head)
        if heading:
            number = head.get("n") if head is not None else None
            headed.append((f"{number} {heading}" if number else heading, _page(head)))
    sections: list[Section] = []
    for index, (heading, page) in enumerate(headed):
        later = [p for _, p in headed[index + 1 :] if p is not None]
        sections.append(
            Section(
                type=section_type(heading),
                heading=heading,
                page_start=page,
                page_end=later[0] if later and page is not None and later[0] >= page else page,
            )
        )
    references: list[Reference] = []
    for bibl in root.findall(".//tei:back//tei:listBibl/tei:biblStruct", NS):
        title = _text(bibl.find("tei:analytic/tei:title", NS)) or _text(
            bibl.find("tei:monogr/tei:title", NS)
        )
        authors = [
            " ".join(
                part
                for part in (
                    _text(person.find("tei:forename", NS)),
                    _text(person.find("tei:surname", NS)),
                )
                if part
            )
            for person in bibl.findall(".//tei:author/tei:persName", NS)
        ]
        when = bibl.find(".//tei:imprint/tei:date", NS)
        found = _YEAR.search((when.get("when") or _text(when)) if when is not None else "")
        doi = _text(bibl.find(".//tei:idno[@type='DOI']", NS)) or None
        raw = _text(bibl.find("tei:note[@type='raw_reference']", NS))
        references.append(
            Reference(
                raw_text=raw or title,
                title=title or None,
                authors=[a for a in authors if a],
                year=int(found.group(1)) if found else None,
                doi=doi.lower() if doi else None,
                page=_page(bibl),
            )
        )
    return Structure(sections=sections, references=references)
