"""Find every pdf.js selection in PDFium's text and check that it lands in the same place."""

import json
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path

import pypdfium2 as pdfium
from pypdfium2 import raw
from rapidfuzz import fuzz

OUT = Path(__file__).parent.parent / "out"
SLACK = 2.0  # points: text-layer boxes are the line height, glyph boxes are the ink


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(str.maketrans({"I": "i", "İ": "i", "ı": "i"})).casefold()
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def key_of(text: str) -> tuple[str, list[int]]:
    """Letters and digits only, folded, with the index each came from."""
    key: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        for folded in fold(char):
            if folded.isalnum():
                key.append(folded)
                origin.append(index)
    return "".join(key), origin


def occurrences(haystack: str, needle: str) -> list[int]:
    found: list[int] = []
    at = haystack.find(needle)
    while at != -1:
        found.append(at)
        at = haystack.find(needle, at + 1)
    return found


def page_chars(text_page: object) -> str:
    """One Python character per PDFium character, so an index is also a box index."""
    count = raw.FPDFText_CountChars(text_page)
    return "".join(
        chr(raw.FPDFText_GetUnicode(text_page, i) or 32) for i in range(count)
    )


def main() -> int:
    by_file: dict[str, list[dict]] = defaultdict(list)
    for selection in json.loads((OUT / "selections.json").read_text(encoding="utf-8")):
        by_file[selection["file"]].append(selection)
    report: dict[str, dict] = {}
    failures: list[dict] = []
    for name, selections in by_file.items():
        doc = pdfium.PdfDocument(OUT / name)
        pages: dict[int, tuple] = {}
        tally = {
            "selections": len(selections),
            "found": 0,
            "right_place": 0,
            "ambiguous": 0,
            "fuzzy": 0,
        }
        started = time.perf_counter()
        for selection in selections:
            if selection["page"] not in pages:
                # PDFium orders text by the displayed page: read it unrotated. Boxes are in the
                # page's own (unrotated) space either way, as pdf.js's convertToPdfPoint is.
                page = doc[selection["page"]]
                page.set_rotation(0)
                text_page = page.get_textpage()
                text = page_chars(text_page)
                pages[selection["page"]] = (text_page, text, *key_of(text))
            text_page, text, key, origin = pages[selection["page"]]
            needle, _ = key_of(selection["text"])
            spans = [(start, start + len(needle)) for start in occurrences(key, needle)]
            if not spans and len(needle) >= 12:
                # A glyph one engine drops or repeats: the closest passage, if close enough.
                close = fuzz.partial_ratio_alignment(needle, key, score_cutoff=85)
                if close is not None:
                    spans = [(close.dest_start, close.dest_end)]
                    tally["fuzzy"] += 1
            starts = spans
            tally["found"] += bool(starts)
            tally["ambiguous"] += len(starts) > 1
            best = 0.0
            for start, end in spans:
                inside = total = 0
                for position in range(start, end):
                    left, bottom, right, top = text_page.get_charbox(
                        origin[position], loose=True
                    )
                    if right <= left:
                        continue
                    total += 1
                    x, y = (left + right) / 2, (bottom + top) / 2
                    inside += any(
                        a - SLACK <= x <= c + SLACK and b - SLACK <= y <= d + SLACK
                        for a, b, c, d in selection["rects"]
                    )
                best = max(best, inside / total if total else 0.0)
            if best >= 0.9:
                tally["right_place"] += 1
            else:
                failures.append(
                    {**selection, "found": len(starts), "overlap": round(best, 2)}
                )
        tally["ms_per_selection"] = round(
            1000 * (time.perf_counter() - started) / max(1, len(selections)), 2
        )
        tally["percent"] = round(
            100 * tally["right_place"] / max(1, len(selections)), 1
        )
        report[name] = tally
    total = sum(t["selections"] for t in report.values())
    right = sum(t["right_place"] for t in report.values())
    report["TOTAL"] = {
        "selections": total,
        "right_place": right,
        "percent": round(100 * right / total, 2),
    }
    (OUT.parent / "RESULTS.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    for name, tally in report.items():
        print(name, tally)
    for failure in failures[:8]:
        print(json.dumps({**failure, "rects": failure["rects"][:3]}, ensure_ascii=True))
    return 0 if right / total >= 0.95 else 1


if __name__ == "__main__":
    sys.exit(main())
