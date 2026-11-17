"""Formatted bibliographies: papers rendered with a bundled CSL style (Task 39, ADR 0019).

The styles come from the CSL project (CC BY-SA 3.0, attribution in `docs/licenses.md`) and the
locales from citeproc-py's own copy. citeproc-py has no type hints, so this module and
`csl_compat` are the only places that touch it.
"""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportMissingTypeStubs=false
# pyright: reportAttributeAccessIssue=false

import html
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any

from citeproc import (
    Citation,
    CitationItem,
    CitationStylesBibliography,
    CitationStylesStyle,
    formatter,
)
from citeproc.source.json import CiteProcJSON
from lxml import etree

from tez.modules.export import csl_compat
from tez.modules.export.writers import ExportPaper
from tez.modules.library.models import ThesisType, VenueType

csl_compat.install()

_STYLES_DIR = Path(__file__).parent / "styles"
_CSL_NS = "http://purl.org/net/xbiblio/csl"


class CslStyle(StrEnum):
    APA = "apa"
    MLA = "mla"
    CHICAGO_AUTHOR_DATE = "chicago-author-date"
    CHICAGO_NOTES = "chicago-notes"
    VANCOUVER = "vancouver"
    IEEE = "ieee"


class CslLocale(StrEnum):
    TR = "tr-TR"
    EN = "en-US"


_STYLE_FILES: dict[CslStyle, str] = {
    CslStyle.APA: "apa.csl",
    CslStyle.MLA: "modern-language-association.csl",
    CslStyle.CHICAGO_AUTHOR_DATE: "chicago-author-date.csl",
    CslStyle.CHICAGO_NOTES: "chicago-notes-bibliography.csl",
    CslStyle.VANCOUVER: "nlm-citation-sequence.csl",
    CslStyle.IEEE: "ieee.csl",
}

# Whether a period or comma goes inside a closing quotation mark (the locale's
# `punctuation-in-quote`; citeproc-py does not apply it).
_PUNCTUATION_IN_QUOTE: dict[CslLocale, bool] = {CslLocale.TR: False, CslLocale.EN: True}

_CSL_TYPES: dict[VenueType | None, str] = {
    VenueType.JOURNAL: "article-journal",
    VenueType.CONFERENCE: "paper-conference",
    VenueType.CHAPTER: "chapter",
    VenueType.BOOK: "book",
    VenueType.THESIS: "thesis",
    VenueType.REPORT: "report",
    VenueType.PREPRINT: "article",
    VenueType.OTHER: "document",
    None: "document",
}

# Where `venue` goes: the work it is part of, or who published it.
_PUBLISHER_VENUES = {VenueType.BOOK, VenueType.THESIS, VenueType.REPORT}

_GENRES: dict[CslLocale, dict[ThesisType, str]] = {
    CslLocale.TR: {ThesisType.MASTERS: "Yüksek lisans tezi", ThesisType.DOCTORAL: "Doktora tezi"},
    CslLocale.EN: {
        ThesisType.MASTERS: "Master's thesis",
        ThesisType.DOCTORAL: "Doctoral dissertation",
    },
}

_PAGE_DASHES = re.compile(r"\s*[-\N{EN DASH}\N{EM DASH}]+\s*")
_LANGUAGE_CODE = re.compile(r"^[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]+)*$")
_QUOTE_THEN_PUNCTUATION = re.compile("\N{RIGHT DOUBLE QUOTATION MARK}([.,])")


@dataclass(frozen=True)
class RenderedEntry:
    citekey: str
    # Inline HTML: escaped text with <i>, <b>, <sup>, <sub> and small-caps <span>.
    html: str
    text: str


def _language(value: str | None) -> str | None:
    """A BCP 47 tag ("tr", "en-GB") for CSL, or None when the stored value is not one."""
    if value and _LANGUAGE_CODE.match(value.strip()):
        return value.strip().replace("_", "-").lower()
    return None


def csl_item(paper: ExportPaper, locale: CslLocale, item_id: str) -> dict[str, Any]:
    """A paper as CSL-JSON."""
    item: dict[str, Any] = {
        "id": item_id,
        "type": _CSL_TYPES[paper.venue_type],
        "title": " ".join(paper.title.split()),
    }
    authors: list[dict[str, str]] = []
    for author in paper.authors:
        if author.family:
            name = {"family": author.family}
            if author.given:
                name["given"] = author.given
            authors.append(name)
        else:
            authors.append({"literal": author.display_name})
    if authors:
        item["author"] = authors
    if paper.year is not None:
        item["issued"] = {"date-parts": [[paper.year]]}
    if paper.venue:
        venue_field = "publisher" if paper.venue_type in _PUBLISHER_VENUES else "container-title"
        item[venue_field] = paper.venue
    if paper.venue_type is VenueType.THESIS and paper.thesis_type is not None:
        item["genre"] = _GENRES[locale][paper.thesis_type]
    for field, value in (("volume", paper.volume), ("issue", paper.issue)):
        if value:
            item[field] = value
    if paper.pages:
        item["page"] = _PAGE_DASHES.sub("-", paper.pages)
    if paper.doi:
        item["DOI"] = paper.doi
    if paper.isbn:
        item["ISBN"] = paper.isbn
    if paper.arxiv and paper.venue_type is VenueType.PREPRINT:
        item["number"] = f"arXiv:{paper.arxiv}"
    if paper.url:
        item["URL"] = paper.url
    # Title case is for English only (CSL). A paper whose language is not known is taken to
    # be in the bibliography's language, so a Turkish list never gives "Eğitim Ve Bilim".
    item["language"] = _language(paper.language) or locale.value.split("-")[0]
    return item


def _escaped(value: Any) -> Any:
    """CSL-JSON with every string HTML-escaped: citeproc-py's HTML output passes field text
    through as markup."""
    if isinstance(value, str):
        return html.escape(value, quote=False)
    if isinstance(value, list):
        return [_escaped(v) for v in value]
    if isinstance(value, dict):
        return {k: _escaped(v) for k, v in value.items()}
    return value


@cache
def _style_xml(style: CslStyle) -> bytes:
    """The bundled style, with a space after the first field of styles that align it
    (`second-field-align`), which citeproc-py prints with no gap."""
    tree = etree.parse(_STYLES_DIR / _STYLE_FILES[style])
    for layout in tree.iterfind(
        f"{{{_CSL_NS}}}bibliography[@second-field-align]/{{{_CSL_NS}}}layout"
    ):
        first = next(layout.iterchildren(etree.Element), None)
        if first is not None:
            first.set("suffix", (first.get("suffix") or "") + " ")
    return etree.tostring(tree, encoding="utf-8", xml_declaration=True)


def _punctuation_in_quote(text: str, locale: CslLocale) -> str:
    if not _PUNCTUATION_IN_QUOTE[locale]:
        return text
    return _QUOTE_THEN_PUNCTUATION.sub("\\1\N{RIGHT DOUBLE QUOTATION MARK}", text)


def _render(
    style: CslStyle, locale: CslLocale, source: Any, keys: Sequence[str], output: Any
) -> tuple[list[str], list[str]]:
    parsed = CitationStylesStyle(io.BytesIO(_style_xml(style)), locale=locale.value, validate=False)
    bibliography = CitationStylesBibliography(parsed, source, output)
    for key in keys:
        bibliography.register(Citation([CitationItem(key)]))
    bibliography.sort()
    with csl_compat.turkish_locale(locale is CslLocale.TR):
        entries = [str(entry) for entry in bibliography.bibliography()]
    return list(bibliography.keys), entries


def render(
    style: CslStyle, locale: CslLocale, papers: Sequence[ExportPaper]
) -> list[RenderedEntry]:
    """The bibliography in the style's order (alphabetical, or as given for numbered styles)."""
    if not papers:
        return []
    # citeproc-py lower-cases ids, so papers go in by position, not by citation key.
    ids = [f"item{index}" for index in range(len(papers))]
    by_id = dict(zip(ids, papers, strict=True))
    items = [csl_item(by_id[i], locale, i) for i in ids]
    order, html_entries = _render(
        style, locale, CiteProcJSON([_escaped(item) for item in items]), ids, formatter.html
    )
    _, text_entries = _render(style, locale, CiteProcJSON(items), ids, formatter.plain)
    return [
        RenderedEntry(
            citekey=by_id[key].citekey,
            html=_punctuation_in_quote(markup.strip(), locale),
            text=_punctuation_in_quote(text.strip(), locale),
        )
        for key, markup, text in zip(order, html_entries, text_entries, strict=True)
    ]
