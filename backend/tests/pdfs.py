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
    return _write(objects)


def _write(objects: list[bytes], trailer: bytes = b"/Root 1 0 R /Info 4 0 R") -> bytes:
    """The file itself: header, numbered objects, cross-reference table."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d %s >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        trailer,
        xref,
    )
    return bytes(out)


def broken_pdf() -> bytes:
    """Starts like a PDF and is not one: what a cut-off download looks like."""
    return b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R"


def make_text_pdf(pages: list[list[str]], *, rotate: int = 0, raw_codes: bool = False) -> bytes:
    """A PDF with real text lines in any script: each character gets its own font code and a
    Unicode map, as LaTeX and Word write them.

    `rotate` displays every page turned by that angle. With `raw_codes` the font has no Unicode
    map and the lines are sent as Latin-1 bytes: a font whose ligatures have no names.
    """
    alphabet = sorted({char for lines in pages for line in lines for char in line})
    codes = {char: 33 + index for index, char in enumerate(alphabet)}
    assert len(codes) < 200, "one byte per character"
    mapping = "\n".join(f"<{code:02x}> <{ord(char):04x}>" for char, code in codes.items())
    cmap = (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        "/CMapName /TEz def /CMapType 2 def\n"
        "1 begincodespacerange <00> <ff> endcodespacerange\n"
        f"{len(codes)} beginbfchar\n{mapping}\nendbfchar\nendcmap end end"
    ).encode()
    to_unicode = b"" if raw_codes else b" /ToUnicode 5 0 R"
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /FirstChar 0 /LastChar 255 /Widths ["
        + b"600 " * 256
        + b"]"
        + to_unicode
        + b" >>",
        b"<< /Producer (TEz tests) >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(cmap), cmap),
    ]
    kids: list[int] = []
    for lines in pages:
        shown: list[bytes] = [b"BT /F1 11 Tf 14 TL 72 720 Td"]
        for line in lines:
            data = line.encode("latin-1") if raw_codes else bytes(codes[char] for char in line)
            shown.append(b"<" + data.hex().encode() + b"> Tj T*")
        stream = b"\n".join([*shown, b"ET"])
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Rotate %d "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % (rotate, content)
        )
        kids.append(len(objects))
    listed = b" ".join(b"%d 0 R" % kid for kid in kids)
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (listed, len(kids))
    return _write(objects)


def encrypted_pdf() -> bytes:
    """A PDF that needs a password nobody has."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
        b"<< /Filter /Standard /V 1 /R 2 /P -44 /O <%s> /U <%s> >>" % (b"ab" * 32, b"cd" * 32),
    ]
    ident = b"00112233445566778899aabbccddeeff"
    return _write(objects, b"/Root 1 0 R /Encrypt 4 0 R /ID [<%s> <%s>]" % (ident, ident))
