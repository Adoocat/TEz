"""Find a quoted passage in a text (ADR 0030).

Texts are compared by their key: letters and digits only, folded. Whitespace, hyphens, line
breaks, quotation marks, ligatures and accents do not matter, and every key character knows the
position it came from, so a match maps back to exact characters.

A wrong place is worse than none (CLAUDE.md rule 2): what is short must match exactly and be
unique or stand in the same context; only long passages may match approximately.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

from tez.shared.text import fold_with_map

# Letters of context compared on either side.
CONTEXT = 48
# A passage this long that occurs once is itself, wherever it stands.
_LONG = 20
# A closer look (one glyph read differently) is only for passages at least this long.
_FUZZY_MIN = 24
_FUZZY_SCORE = 90.0
# How alike the surroundings must be for a place to be trusted by them.
_CONTEXT_SCORE = 60.0
# Two places this close in likeness cannot be told apart.
_MARGIN = 5.0


@dataclass(frozen=True)
class Key:
    text: str
    # For each character of `text`, its position in the original.
    origin: Sequence[int]


def key_of(text: str) -> Key:
    folded, origin = fold_with_map(text)
    kept = [index for index, char in enumerate(folded) if char.isalnum()]
    return Key("".join(folded[i] for i in kept), [origin[i] for i in kept])


@dataclass(frozen=True)
class Quote:
    exact: str
    prefix: str = ""
    suffix: str = ""


@dataclass(frozen=True)
class Place:
    """Where a passage is: a text (by its position in the list searched) and its characters."""

    index: int
    start: int
    end: int
    # How alike the surroundings are, 0 to 100.
    context: float


def _occurrences(haystack: str, needle: str) -> list[int]:
    found: list[int] = []
    at = haystack.find(needle)
    while at != -1:
        found.append(at)
        at = haystack.find(needle, at + 1)
    return found


class _Wanted:
    def __init__(self, quote: Quote) -> None:
        self.key = key_of(quote.exact).text
        self.prefix = key_of(quote.prefix).text[-CONTEXT:]
        self.suffix = key_of(quote.suffix).text[:CONTEXT]

    def context(self, key: Key, start: int, end: int) -> float:
        """Likeness of what stands before and after; 0 when nothing is known about it."""
        scores: list[float] = []
        if self.prefix:
            before = key.text[max(0, start - len(self.prefix)) : start]
            scores.append(fuzz.ratio(self.prefix, before))
        if self.suffix:
            after = key.text[end : end + len(self.suffix)]
            scores.append(fuzz.ratio(self.suffix, after))
        return sum(scores) / len(scores) if scores else 0.0

    def place(self, index: int, key: Key, start: int, end: int) -> Place:
        return Place(
            index=index,
            start=key.origin[start],
            end=key.origin[end - 1] + 1,
            context=self.context(key, start, end),
        )


def _exact(wanted: _Wanted, keys: Sequence[Key]) -> list[Place]:
    return [
        wanted.place(index, key, start, start + len(wanted.key))
        for index, key in enumerate(keys)
        for start in _occurrences(key.text, wanted.key)
    ]


def _whole_words(key: Key, start: int, end: int) -> tuple[int, int]:
    """The alignment is as long as the passage was; where words grew it stops inside one."""
    while start > 0 and key.origin[start] - key.origin[start - 1] <= 1:
        start -= 1
    while end < len(key.text) and key.origin[end] - key.origin[end - 1] <= 1:
        end += 1
    return start, end


def _close(wanted: _Wanted, keys: Sequence[Key]) -> Place | None:
    """The best approximate match, if it is good enough and clearly the best."""
    if len(wanted.key) < _FUZZY_MIN:
        return None
    scored: list[tuple[float, Place]] = []
    for index, key in enumerate(keys):
        # Aligning is only defined with the passage as the shorter text.
        if len(key.text) < len(wanted.key):
            continue
        found = fuzz.partial_ratio_alignment(wanted.key, key.text, score_cutoff=_FUZZY_SCORE)
        if found is not None and found.dest_end > found.dest_start:
            start, end = _whole_words(key, found.dest_start, found.dest_end)
            scored.append((found.score, wanted.place(index, key, start, end)))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored or (len(scored) > 1 and scored[0][0] - scored[1][0] < _MARGIN):
        return None
    score, place = scored[0]
    trusted = score >= 95.0 or place.context >= _CONTEXT_SCORE
    return place if trusted else None


def locate_on_page(text: str, quote: Quote, *, occurrence: int | None = None) -> Place | None:
    """A passage somebody just selected on this page: it is there, the question is where.

    Repeats are told apart by their surroundings, then by `occurrence` (which of them, from 0,
    in reading order).
    """
    wanted = _Wanted(quote)
    if not wanted.key:
        return None
    key = key_of(text)
    places = _exact(wanted, [key])
    if not places:
        return _close(wanted, [key])
    best = max(place.context for place in places)
    alike = [place for place in places if best - place.context < _MARGIN]
    if len(alike) == 1:
        return alike[0]
    if occurrence is not None and 0 <= occurrence < len(places) and places[occurrence] in alike:
        return places[occurrence]
    return alike[0]


def relocate(texts: Sequence[str], quote: Quote, *, home: int) -> Place | None:
    """A passage in another version of the document: anywhere, or nowhere.

    `home` is the page it used to be on. None unless the place can be trusted.
    """
    wanted = _Wanted(quote)
    if not wanted.key:
        return None
    keys = [key_of(text) for text in texts]
    places = _exact(wanted, keys)
    if not places:
        return _close(wanted, keys)
    if len(places) == 1:
        only = places[0]
        return only if len(wanted.key) >= _LONG or only.context >= _CONTEXT_SCORE else None
    best = max(place.context for place in places)
    if best < _CONTEXT_SCORE:
        return None
    alike = [place for place in places if best - place.context < _MARGIN]
    if len(alike) == 1:
        return alike[0]
    at_home = [place for place in alike if place.index == home]
    return at_home[0] if len(at_home) == 1 else None
