"""What a matrix cell holds, and how it changes when its column's type does (Task 51, ADR 0035).

A cell holds a value of its column's type. When the type or the options change, every value
is written out as text and read back as the new type. A value that cannot be read back is not
dropped: the cell keeps that text, marked as not converted, until the user fixes it or a later
change can read it. Nothing here touches the database.
"""

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict, cast

from tez.shared.text import fold


class DataType(StrEnum):
    TEXT = "text"
    NUMBER = "number"
    ENUM = "enum"
    MULTI_ENUM = "multi_enum"
    BOOL = "bool"


class Option(TypedDict):
    """A choice of an enum or multi-enum column. Cells keep the id, so a label can change."""

    id: str
    label: str


type Value = str | int | float | bool | list[str]

MAX_TEXT = 10_000
# Several choices written as text, and read back: "Survey; Interview".
CHOICE_SEPARATOR = "; "
_CHOICE_SPLIT = re.compile(r"\s*[;\n]\s*")
_NUMBER = re.compile(r"([+-]?)(\d+)(?:[.,](\d+))?")
_TRUE = frozenset({"true", "yes", "y", "evet", "e", "var", "1", "x", "✓"})
_FALSE = frozenset({"false", "no", "n", "hayir", "h", "yok", "0", "-", "✗"})


class InvalidValue(ValueError):
    """A value that does not fit its column."""


@dataclass(frozen=True)
class Words:
    """How yes and no are written when a yes/no column becomes text: the user's language."""

    true: str = "yes"
    false: str = "no"


PLAIN = Words()


@dataclass(frozen=True)
class Cell:
    """A cell's content: a value, or the text kept because it could not be converted."""

    value: Value | None
    kept_text: str | None = None

    @property
    def converted(self) -> bool:
        return self.kept_text is None


# --- checking what the user writes ----------------------------------------------------------


def check(data_type: DataType, value: object, options: Sequence[Option]) -> Value | None:
    """The value as stored, or None for "empty". Raises InvalidValue if it does not fit."""
    if value is None:
        return None
    match data_type:
        case DataType.TEXT:
            if not isinstance(value, str):
                raise InvalidValue("text expected")
            text = value.strip()
            if len(text) > MAX_TEXT:
                raise InvalidValue("text too long")
            return text or None
        case DataType.NUMBER:
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise InvalidValue("number expected")
            if not math.isfinite(value):
                raise InvalidValue("finite number expected")
            return _tidy_number(value)
        case DataType.BOOL:
            if not isinstance(value, bool):
                raise InvalidValue("true or false expected")
            return value
        case DataType.ENUM:
            if not isinstance(value, str) or value not in _ids(options):
                raise InvalidValue("one of the column's options expected")
            return value
        case DataType.MULTI_ENUM:
            if not isinstance(value, list):
                raise InvalidValue("a list of the column's options expected")
            chosen = [v for v in cast(list[object], value) if isinstance(v, str)]
            if len(chosen) != len(cast(list[object], value)):
                raise InvalidValue("a list of the column's options expected")
            known = _ids(options)
            if any(v not in known for v in chosen) or len(set(chosen)) != len(chosen):
                raise InvalidValue("each of the column's options at most once expected")
            # In the column's order, so equal choices look equal.
            return [option["id"] for option in options if option["id"] in chosen] or None


def _ids(options: Sequence[Option]) -> set[str]:
    return {option["id"] for option in options}


def _tidy_number(value: float) -> int | float:
    return int(value) if float(value).is_integer() and abs(value) < 2**53 else float(value)


# --- writing out and reading back -----------------------------------------------------------


def render(data_type: DataType, value: Value, options: Sequence[Option], words: Words) -> str:
    """A value as text, the way a person would write it in a table."""
    labels = {option["id"]: option["label"] for option in options}
    match data_type:
        case DataType.TEXT:
            return str(value)
        case DataType.NUMBER:
            assert isinstance(value, int | float) and not isinstance(value, bool)
            return str(_tidy_number(value))
        case DataType.BOOL:
            return words.true if value else words.false
        case DataType.ENUM:
            assert isinstance(value, str)
            return labels.get(value, value)
        case DataType.MULTI_ENUM:
            assert isinstance(value, list)
            return CHOICE_SEPARATOR.join(labels.get(v, v) for v in value)


def parse(data_type: DataType, text: str, options: Sequence[Option]) -> Value | None:
    """Text read as a value of the type; None when it cannot be read without guessing."""
    text = text.strip()
    match data_type:
        case DataType.TEXT:
            return text
        case DataType.NUMBER:
            return _parse_number(text)
        case DataType.BOOL:
            folded = fold(text)
            return True if folded in _TRUE else False if folded in _FALSE else None
        case DataType.ENUM:
            return _option_for(text, options)
        case DataType.MULTI_ENUM:
            chosen: list[str] = []
            for piece in split_choices(text):
                found = _option_for(piece, options)
                if found is None:
                    return None
                if found not in chosen:
                    chosen.append(found)
            return [option["id"] for option in options if option["id"] in chosen] or None


def _parse_number(text: str) -> int | float | None:
    """Plain numbers only, with a decimal point or comma. "1.420" is left alone: in Turkish
    it is one thousand four hundred and twenty, in English one point four two."""
    found = _NUMBER.fullmatch(text.replace(" ", ""))
    if found is None:
        return None
    sign, whole, fraction = found.groups()
    if fraction is not None and len(fraction) == 3 and whole.lstrip("0") != "":
        return None
    number = float(f"{sign}{whole}.{fraction or '0'}")
    return _tidy_number(number)


def _option_for(text: str, options: Sequence[Option]) -> str | None:
    wanted = fold(text)
    return next((option["id"] for option in options if fold(option["label"]) == wanted), None)


def split_choices(text: str) -> list[str]:
    return [piece for piece in _CHOICE_SPLIT.split(text.strip()) if piece]


def labels_in(texts: Iterable[str], multi: bool) -> list[str]:
    """The distinct choices written in some texts, in the order first met: the options a
    column gets when it becomes an enum without being told which."""
    found: dict[str, str] = {}
    for text in texts:
        for piece in split_choices(text) if multi else [text.strip()]:
            if piece:
                found.setdefault(fold(piece), piece)
    return list(found.values())


def convert(
    cell: Cell,
    old: tuple[DataType, Sequence[Option]],
    new: tuple[DataType, Sequence[Option]],
    words: Words = PLAIN,
) -> Cell:
    """The cell under the column's new type and options. What cannot be read back is kept
    as text; text kept from an earlier change is tried again."""
    (old_type, old_options), (new_type, new_options) = old, new
    kept = _same_choices(cell.value, old_type, new_type, _ids(new_options))
    if kept is not None:
        return Cell(kept)
    if cell.value is None:
        text = cell.kept_text
    else:
        text = render(old_type, cell.value, old_options, words)
    if text is None or text.strip() == "":
        return Cell(None)
    value = parse(new_type, text, new_options)
    if value is None:
        return Cell(None, kept_text=text)
    return Cell(value)


def _same_choices(
    value: Value | None, old_type: DataType, new_type: DataType, new_ids: set[str]
) -> Value | None:
    """The value unchanged when the type stays or only grows from one choice to several:
    options are matched by id, so a renamed option keeps its cells."""
    choices = {DataType.ENUM, DataType.MULTI_ENUM}
    if value is None:
        return None
    if old_type == new_type and new_type not in choices:
        return value
    if old_type not in choices or new_type not in choices:
        return None
    ids = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    if not ids or any(i not in new_ids for i in ids):
        return None
    if new_type == DataType.ENUM:
        return ids[0] if len(ids) == 1 else None
    return list(ids)
