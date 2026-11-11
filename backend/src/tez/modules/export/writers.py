"""BibTeX and RIS text from papers. Both read back through our own importers (round-trip tests).

BibTeX keeps Unicode as it is (biber and modern BibTeX read UTF-8) and escapes only the
characters LaTeX treats as commands. Titles are wrapped in an extra pair of braces, so a style
cannot lower-case "LLM" or "BERT".
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from tez.modules.library.models import VenueType

# Page ranges: a hyphen, an en dash or an em dash, with any spaces around.
_DASHES = re.compile(r"\s*[-" + "\N{EN DASH}\N{EM DASH}" + r"]+\s*")
_LATEX_SPECIAL = re.compile(r"[\\{}&%$#_~^]")
_LATEX_REPLACEMENT = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


@dataclass(frozen=True)
class ExportAuthor:
    display_name: str
    family: str | None
    given: str | None


@dataclass(frozen=True)
class ExportPaper:
    citekey: str
    title: str
    authors: tuple[ExportAuthor, ...]
    year: int | None
    venue: str | None
    venue_type: VenueType | None
    volume: str | None
    issue: str | None
    pages: str | None
    doi: str | None
    arxiv: str | None
    isbn: str | None
    url: str | None
    abstract: str | None
    language: str | None


def _latex(text: str) -> str:
    return _LATEX_SPECIAL.sub(lambda m: _LATEX_REPLACEMENT[m.group(0)], " ".join(text.split()))


def _bib_author(author: ExportAuthor) -> str:
    if author.family:
        family = _latex(author.family)
        # Multi-word family names ("van der Berg") must stay one name to BibTeX.
        return f"{family}, {_latex(author.given)}" if author.given else family
    # No parts known: braces make BibTeX take it whole (a group or a mononym).
    return "{" + _latex(author.display_name) + "}"


_BIB_TYPES: dict[VenueType | None, tuple[str, str | None]] = {
    VenueType.JOURNAL: ("article", "journal"),
    VenueType.CONFERENCE: ("inproceedings", "booktitle"),
    VenueType.CHAPTER: ("incollection", "booktitle"),
    VenueType.BOOK: ("book", "publisher"),
    VenueType.THESIS: ("phdthesis", "school"),
    VenueType.REPORT: ("techreport", "institution"),
    VenueType.PREPRINT: ("misc", "howpublished"),
    VenueType.OTHER: ("misc", "howpublished"),
    None: ("misc", "howpublished"),
}


def bibtex_entry(paper: ExportPaper) -> str:
    entry_type, venue_field = _BIB_TYPES[paper.venue_type]
    fields: list[tuple[str, str]] = [("title", "{" + _latex(paper.title) + "}")]
    if paper.authors:
        fields.append(("author", " and ".join(_bib_author(a) for a in paper.authors)))
    if paper.year is not None:
        fields.append(("year", str(paper.year)))
    if paper.venue and venue_field:
        fields.append((venue_field, _latex(paper.venue)))
    for name, value in (("volume", paper.volume), ("number", paper.issue)):
        if value:
            fields.append((name, _latex(value)))
    if paper.pages:
        fields.append(("pages", _latex(_DASHES.sub("--", paper.pages))))
    if paper.doi:
        fields.append(("doi", paper.doi))
    if paper.arxiv:
        fields += [("eprint", paper.arxiv), ("archiveprefix", "arXiv")]
    if paper.isbn:
        fields.append(("isbn", paper.isbn))
    if paper.url:
        fields.append(("url", paper.url))
    if paper.language:
        fields.append(("language", _latex(paper.language)))
    if paper.abstract:
        fields.append(("abstract", _latex(paper.abstract)))
    body = ",\n".join(f"  {name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{paper.citekey},\n{body}\n}}\n"


def to_bibtex(papers: Iterable[ExportPaper]) -> str:
    return "\n".join(bibtex_entry(paper) for paper in papers)


_RIS_TYPES: dict[VenueType | None, str] = {
    VenueType.JOURNAL: "JOUR",
    VenueType.CONFERENCE: "CPAPER",
    VenueType.CHAPTER: "CHAP",
    VenueType.BOOK: "BOOK",
    VenueType.THESIS: "THES",
    VenueType.REPORT: "RPRT",
    VenueType.PREPRINT: "UNPB",
    VenueType.OTHER: "GEN",
    None: "GEN",
}


def _ris_line(tag: str, value: str) -> str:
    return f"{tag}  - {' '.join(value.split())}"


def ris_entry(paper: ExportPaper) -> str:
    lines = [_ris_line("TY", _RIS_TYPES[paper.venue_type]), _ris_line("ID", paper.citekey)]
    lines.append(_ris_line("TI", paper.title))
    for author in paper.authors:
        name = (
            f"{author.family}, {author.given}"
            if author.family and author.given
            else (author.family or author.display_name)
        )
        lines.append(_ris_line("AU", name))
    if paper.year is not None:
        lines.append(_ris_line("PY", str(paper.year)))
    if paper.venue:
        lines.append(
            _ris_line("JO" if paper.venue_type is VenueType.JOURNAL else "T2", paper.venue)
        )
    if paper.volume:
        lines.append(_ris_line("VL", paper.volume))
    if paper.issue:
        lines.append(_ris_line("IS", paper.issue))
    if paper.pages:
        start, _, end = _DASHES.sub("-", paper.pages).partition("-")
        lines.append(_ris_line("SP", start))
        if end:
            lines.append(_ris_line("EP", end))
    if paper.doi:
        lines.append(_ris_line("DO", paper.doi))
    if paper.isbn:
        lines.append(_ris_line("SN", paper.isbn))
    if paper.url:
        lines.append(_ris_line("UR", paper.url))
    if paper.language:
        lines.append(_ris_line("LA", paper.language))
    if paper.abstract:
        lines.append(_ris_line("AB", paper.abstract))
    lines.append("ER  - ")
    return "\n".join(lines) + "\n"


def to_ris(papers: Iterable[ExportPaper]) -> str:
    return "\n".join(ris_entry(paper) for paper in papers)
