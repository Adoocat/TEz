"""Generate a synthetic N-page, two-column "paper" PDF (no dependencies).

usage: python gen_pdf.py [out_path] [pages]
default: %TEMP%/tez-s1/sample-300.pdf, 300 pages

Each page has ~110 text lines (a realistic text layer for pdf.js) and every
third page has a vector "figure". Text is fictional filler.
"""

from __future__ import annotations

import os
import random
import sys
import zlib

WORDS = (
    "large language models code review pull request reviewer comment defect "
    "precision recall benchmark dataset evaluation empirical study repository "
    "static analysis prompt context retrieval augmentation developer feedback "
    "maintainability latency annotation agreement baseline threat validity"
).split()


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def page_stream(n: int, rng: random.Random) -> bytes:
    ops: list[str] = ["BT /F2 14 Tf 56 800 Td", f"(Section {n // 10 + 1}.{n % 10 + 1}  Synthetic page {n + 1}) Tj ET"]
    for col, x in enumerate((56, 310)):
        ops.append(f"BT /F1 9 Tf 11 TL {x} 770 Td")
        lines = 30 if (n % 3 == 0 and col == 1) else 66
        for _ in range(lines):
            line = " ".join(rng.choice(WORDS) for _ in range(rng.randint(5, 8)))
            ops.append(f"({esc(line)}) Tj T*")
        ops.append("ET")
    if n % 3 == 0:  # simple vector figure in the right column
        ops.append("0.2 0.3 0.5 RG 1 w 310 120 230 300 re S")
        for i in range(12):
            h = rng.randint(20, 260)
            ops.append(f"0.12 0.23 0.37 rg {318 + i * 18} 130 12 {h} re f")
        ops.append("BT /F1 8 Tf 310 108 Td (Figure: synthetic bar chart) Tj ET")
    ops.append(f"BT /F1 8 Tf 290 30 Td ({n + 1}) Tj ET")
    return "\n".join(ops).encode("latin-1")


def build(pages: int) -> bytes:
    rng = random.Random(42)
    objs: list[bytes] = []  # index i -> object number i+1

    def add(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    catalog = add(b"")  # placeholder, filled later
    pages_obj = add(b"")
    f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
    f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    kids: list[int] = []
    for n in range(pages):
        data = zlib.compress(page_stream(n, rng))
        content = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream")
        kids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>" % (pages_obj, content, f1, f2)
            )
        )
    objs[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
    objs[pages_obj - 1] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (
        pages,
        b" ".join(b"%d 0 R" % k for k in kids),
    )

    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref)
    return bytes(out)


def main() -> int:
    default = os.path.join(os.environ.get("TEMP", "."), "tez-s1", "sample-300.pdf")
    path = sys.argv[1] if len(sys.argv) > 1 else default
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    data = build(pages)
    with open(path, "wb") as f:
        f.write(data)
    print(f"{path}: {pages} pages, {len(data) / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
