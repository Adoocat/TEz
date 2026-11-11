"""Small PDFs written by hand for tests: no binary fixtures in the repo (CLAUDE.md)."""


def make_pdf(pages: int = 1, *, text: str | None = "TEz test page", tag: str = "") -> bytes:
    """A valid PDF with `pages` pages, each showing `text` (or nothing, like a scan).

    `tag` goes into the document info, so two PDFs with the same pages differ in bytes.
    """
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # the page tree, filled in once the page numbers are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Producer (TEz tests {tag}) >>".encode(),
    ]
    page_numbers: list[int] = []
    for index in range(pages):
        line = f"{text} {index + 1}" if text is not None else ""
        stream = f"BT /F1 18 Tf 72 720 Td ({line}) Tj ET".encode() if text is not None else b""
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content_number = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % content_number
        )
        page_numbers.append(len(objects))
    kids = " ".join(f"{n} 0 R" for n in page_numbers)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 4 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def broken_pdf() -> bytes:
    """Starts like a PDF and is not one: what a cut-off download looks like."""
    return b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R"
