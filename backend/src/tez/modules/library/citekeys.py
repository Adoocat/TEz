"""Citation keys in the style most LaTeX users know: `yilmaz2024automated` (plan, `citekey`).

A key is made when a paper enters the library and is never changed by the app afterwards: a
thesis may already cite it. The user can edit it. Keys are ASCII (BibTeX is picky), from the
first author's family name, the year and the first meaningful title word. A clash gets a
letter: `yilmaz2024automated`, `yilmaz2024automateda`, `...b`.
"""

import re
import string
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from tez.modules.library.models import Paper

_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "on",
        "in",
        "for",
        "to",
        "and",
        "with",
        "from",
        "by",
        "at",
        "as",
        "is",
        "are",
        "towards",
        "toward",
        "via",
        "using",
        "bir",
        "ve",
        "ile",
        "için",
        "bu",
        "da",
        "de",
    ]
)
_TURKISH = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g"})
_NOT_KEY = re.compile(r"[^a-z0-9]+")
_VALID_KEY = re.compile(r"[A-Za-z0-9_:.\-+/]{1,128}")


def ascii_word(text: str) -> str:
    """ "Çelik" -> "celik", "Şahin" -> "sahin": letters and digits only, lower case."""
    decomposed = unicodedata.normalize("NFKD", text.translate(_TURKISH))
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NOT_KEY.sub("", plain.lower())


def base_key(family: str | None, year: int | None, title: str) -> str:
    author = ascii_word(family.split()[-1]) if family and family.split() else ""
    words = [ascii_word(w) for w in title.split()]
    meaningful = next((w for w in words if w and w not in _STOP_WORDS), "")
    key = f"{author or 'anon'}{year or ''}{meaningful}"
    return key[:100]


def is_valid(key: str) -> bool:
    return _VALID_KEY.fullmatch(key) is not None


def unique_key(session: Session, base: str, reserved: set[str] | None = None) -> str:
    """`base`, or `base` plus a letter, not used by any paper nor in `reserved`."""
    stored = session.scalars(select(Paper.citekey).where(Paper.citekey.startswith(base)))
    taken = {key for key in stored if key is not None} | (reserved or set())
    if base not in taken:
        return base
    for letter in string.ascii_lowercase:
        if base + letter not in taken:
            return base + letter
    counter = 2
    while f"{base}{counter}" in taken:
        counter += 1
    return f"{base}{counter}"
