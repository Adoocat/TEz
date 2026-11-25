"""Boxes of a passage on a page, from PDFium. Worker process only, like all PDF reading."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from tez.modules.files.inspection import open_document

Box = tuple[float, float, float, float]


def passage_rects(path: Path, page_index: int, start: int, end: int) -> list[list[float]]:
    """One box per line for the characters `start`..`end` of a page's text (ADR 0030)."""
    document = open_document(path)
    try:
        page = document[page_index]
        try:
            # The same reading order the text was stored in; boxes are unrotated either way.
            page.set_rotation(0)
            text_page = page.get_textpage()
            try:
                return [list(box) for box in merge_lines(_char_boxes(text_page, start, end))]
            finally:
                text_page.close()
        finally:
            page.close()
    finally:
        document.close()


def _char_boxes(text_page: Any, start: int, end: int) -> Iterable[Box]:
    for index in range(start, end):
        left, bottom, right, top = text_page.get_charbox(index, loose=True)
        # Spaces and line ends PDFium made up have no box.
        if right > left and top > bottom:
            yield (left, bottom, right, top)


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Shared length as a part of the shorter span."""
    shared = min(a1, b1) - max(a0, b0)
    return shared / max(min(a1 - a0, b1 - b0), 1e-6)


def merge_lines(boxes: Iterable[Box]) -> list[Box]:
    """Characters in reading order, joined into one box per line; text may run up or down the
    page (a page turned on its side is stored unturned)."""
    lines: list[Box] = []
    before: Box | None = None
    for box in boxes:
        if before is not None:
            size = max(box[2] - box[0], box[3] - box[1])
            same_row = _overlap(before[1], before[3], box[1], box[3]) > 0.5
            beside = same_row and _gap(before[0], before[2], box[0], box[2]) < 4 * size
            same_column = _overlap(before[0], before[2], box[0], box[2]) > 0.5
            below = same_column and _gap(before[1], before[3], box[1], box[3]) < size / 2
            if beside or (below and not same_row):
                line = lines[-1]
                lines[-1] = (
                    min(line[0], box[0]),
                    min(line[1], box[1]),
                    max(line[2], box[2]),
                    max(line[3], box[3]),
                )
                before = box
                continue
        lines.append(box)
        before = box
    return lines


def _gap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(b0 - a1, a0 - b1, 0.0)
