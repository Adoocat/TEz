"""Text normalization, in one place (CLAUDE.md).

SQLite's FTS5 `unicode61` tokenizer and Python's `str.lower` both get Turkish wrong
("I".lower() is "i", but in Turkish it is "ı"). For matching we sidestep the question:
every i-like letter (I, İ, ı, i) folds to "i" and diacritics are dropped, so "IŞIK",
"Işık" and "ışık" all become "isik". Columns such as `paper.title_norm` come from here.
"""

import html
import re
import unicodedata
from functools import lru_cache

_I_VARIANTS = str.maketrans({"I": "i", "İ": "i", "ı": "i"})
_NON_WORD = re.compile(r"[\W_]+")
_NON_ASCII = re.compile(r"[^\x00-\x7f]+")
_MARKUP_TAG = re.compile(r"</?[a-zA-Z][^<>]*>")


def fold(text: str) -> str:
    """Case- and accent-insensitive form of `text`, Turkish-safe."""
    if text.isascii():
        return text.lower()
    text = unicodedata.normalize("NFKC", text).translate(_I_VARIANTS).casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    # Only the few non-ASCII stretches can hold combining marks (whole pages are folded).
    return _NON_ASCII.sub(_drop_combining, decomposed)


def _drop_combining(found: re.Match[str]) -> str:
    return "".join(c for c in found[0] if not unicodedata.combining(c))


@lru_cache(maxsize=4096)
def _fold_char(char: str) -> str:
    return fold(char)


def fold_with_map(text: str) -> tuple[str, list[int]]:
    """`fold(text)`, and for each of its characters the index in `text` it came from. Folding can
    change lengths ("ß" is "ss", a combining accent disappears), so positions need this."""
    folded: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        for out in _fold_char(char):
            folded.append(out)
            origin.append(index)
    return "".join(folded), origin


def normalize_title(title: str) -> str:
    """Folded title with punctuation removed and whitespace collapsed (`title_norm`)."""
    return " ".join(_NON_WORD.sub(" ", fold(title)).split())


def strip_markup(text: str) -> str:
    """Plain text from a metadata field that may hold JATS or HTML tags and entities."""
    return " ".join(html.unescape(_MARKUP_TAG.sub(" ", text)).split())
