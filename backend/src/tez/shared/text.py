"""Text normalization, in one place (CLAUDE.md).

SQLite's FTS5 `unicode61` tokenizer and Python's `str.lower` both get Turkish wrong
("I".lower() is "i", but in Turkish it is "ı"). For matching we sidestep the question:
every i-like letter (I, İ, ı, i) folds to "i" and diacritics are dropped, so "IŞIK",
"Işık" and "ışık" all become "isik". Columns such as `paper.title_norm` come from here.
"""

import re
import unicodedata

_I_VARIANTS = str.maketrans({"I": "i", "İ": "i", "ı": "i"})
_NON_WORD = re.compile(r"[\W_]+")


def fold(text: str) -> str:
    """Case- and accent-insensitive form of `text`, Turkish-safe."""
    text = unicodedata.normalize("NFKC", text).translate(_I_VARIANTS).casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize_title(title: str) -> str:
    """Folded title with punctuation removed and whitespace collapsed (`title_norm`)."""
    return " ".join(_NON_WORD.sub(" ", fold(title)).split())
