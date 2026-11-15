"""Identifier normalization, in one place. Two spellings of an identifier must become one.

Each function returns None for a value that is not such an identifier at all, so one wrong field
from a source cannot wrongly merge two papers.
"""

import re

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_DOI = re.compile(r"10\.\d{4,9}/\S+")
_ARXIV_PREFIX = re.compile(
    r"^(?:https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/|arxiv:|10\.48550/arxiv\.)", re.IGNORECASE
)
_ARXIV_SUFFIX = re.compile(r"(?:\.pdf)?$", re.IGNORECASE)
_ARXIV_VERSION = re.compile(r"v\d+$", re.IGNORECASE)
_ARXIV = re.compile(r"\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]{2})?/\d{7}")
_ISBN = re.compile(r"\d{9}[\dX]|\d{13}")
_PMID = re.compile(r"^(?:pmid:\s*)?(\d{1,9})$", re.IGNORECASE)
_PMCID = re.compile(r"^(?:pmcid:\s*)?(?:pmc)?(\d{1,9})$", re.IGNORECASE)


def normalize_doi(value: str) -> str | None:
    """Lower case, with no resolver prefix or trailing punctuation. DOIs ignore case."""
    doi = _DOI_PREFIX.sub("", value.strip()).lower().rstrip(".,;")
    return doi if _DOI.fullmatch(doi) else None


def normalize_arxiv(value: str) -> str | None:
    """The bare id with no version: every version of a preprint is one paper."""
    text = _ARXIV_PREFIX.sub("", value.strip())
    text = _ARXIV_VERSION.sub("", _ARXIV_SUFFIX.sub("", text)).lower()
    return text if _ARXIV.fullmatch(text) else None


def normalize_isbn(value: str) -> str | None:
    text = re.sub(r"[\s-]", "", value).upper()
    return text if _ISBN.fullmatch(text) else None


def normalize_pmid(value: str) -> str | None:
    """PubMed's id: digits only ("PMID: 123" -> "123")."""
    match = _PMID.match(value.strip())
    return match.group(1).lstrip("0") or None if match else None


def normalize_pmcid(value: str) -> str | None:
    """PubMed Central's id, always with its prefix ("4567" or "pmc4567" -> "PMC4567")."""
    match = _PMCID.match(value.strip())
    return f"PMC{match.group(1)}" if match else None
