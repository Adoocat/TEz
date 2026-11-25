"""Searching text: query words and phrases, FTS5 expressions, and the passage to show.

Texts and queries are folded (`shared.text.fold`), so Turkish letters match both ways.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from tez.shared.text import fold, fold_with_map

# Characters shown either side of the first match.
_CONTEXT = 110

_QUERY_PART = re.compile(r'"([^"]*)"|(\S+)')
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Term:
    """A folded word (or its beginning), or the words of a quoted phrase."""

    words: tuple[str, ...]
    phrase: bool


def parse(query: str) -> list[Term]:
    """Every term must appear. Words match by their beginning ("revi" finds
    "review"); a quoted phrase matches exactly, word by word."""
    terms: list[Term] = []
    for quoted, plain in _QUERY_PART.findall(query):
        words = _WORD.findall(fold(quoted or plain))
        if quoted and words:
            terms.append(Term(tuple(words), phrase=True))
        else:
            # "peer-review" is two words; an unclosed quote is just a word.
            terms.extend(Term((word,), phrase=False) for word in words)
    return terms


def expression(terms: Sequence[Term]) -> str:
    parts: list[str] = []
    for term in terms:
        joined = " ".join(term.words)
        parts.append(f'"{joined}"' if term.phrase else f'"{joined}"*')
    return " ".join(parts)


@dataclass(frozen=True)
class Segment:
    text: str
    hit: bool


def _pattern(terms: Sequence[Term]) -> re.Pattern[str]:
    """Where the terms are in folded text."""
    parts: list[str] = []
    for term in terms:
        words = r"\W+".join(re.escape(word) for word in term.words)
        parts.append(rf"\b{words}\b" if term.phrase else rf"\b{words}\w*")
    return re.compile("|".join(parts))


def passage(shown: str, terms: Sequence[Term]) -> list[Segment]:
    """The part of a text around the first match, cut at word boundaries, with every match
    marked; the beginning when nothing in it matches."""
    folded = fold(shown)
    # Nearly every text folds one to one.
    origin: Sequence[int] = range(len(shown))
    if len(folded) != len(shown):
        folded, origin = fold_with_map(shown)
    found = [match.span() for match in _pattern(terms).finditer(folded)]
    if not found:
        end = _word_edge(shown, 2 * _CONTEXT, 1)
        return [Segment(shown[:end].strip() + ("…" if end < len(shown) else ""), hit=False)]
    spans = [(origin[start], origin[end - 1] + 1) for start, end in found]
    first = spans[0]
    start = _word_edge(shown, first[0] - _CONTEXT, -1)
    end = _word_edge(shown, first[1] + _CONTEXT, 1)
    segments: list[Segment] = []
    at = start
    for left, right in spans:
        if left < at or right > end:
            continue
        if left > at:
            segments.append(Segment(shown[at:left], hit=False))
        segments.append(Segment(shown[left:right], hit=True))
        at = right
    if at < end:
        segments.append(Segment(shown[at:end], hit=False))
    if start > 0:
        segments.insert(0, Segment("…", hit=False))
    if end < len(shown):
        segments.append(Segment("…", hit=False))
    return segments


def _word_edge(shown: str, at: int, direction: int) -> int:
    """The nearest space at or beyond `at`, so no word is cut in half."""
    at = max(0, min(at, len(shown)))
    while 0 < at < len(shown) and not shown[at - 1].isspace():
        at += direction
    return at
