# The XML parts below are written out whole, as the standard has them.
# ruff: noqa: E501
"""A one-sheet .xlsx file, written with the standard library (Task 54).

Enough of Office Open XML for a table: text kept inline (UTF-8, so Turkish letters stay as
they are), numbers as numbers, a bold header row that stays in place, and column widths. No
dependency, so no license to check (rule 6).
"""

import re
import zipfile
from collections.abc import Sequence
from io import BytesIO
from xml.sax.saxutils import escape

type CellValue = str | int | float | None

# Characters XML 1.0 cannot hold; Excel refuses a file that has them.
_NOT_XML = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
_NOT_IN_SHEET_NAME = re.compile(r"[\[\]:*?/\\]")
MAX_WIDTH = 60

_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

# Style 0: plain, wrapped at the top; style 1: bold header.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
</cellXfs>
</styleSheet>"""


def column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def sheet_name(name: str) -> str:
    """A name Excel takes for a sheet: no []:*?/\\, at most 31 characters, not empty."""
    cleaned = _NOT_IN_SHEET_NAME.sub(" ", _NOT_XML.sub("", name)).strip(" '")[:31]
    return cleaned or "Sheet1"


def _cell(ref: str, value: CellValue, style: int) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, int | float):
        return f'<c r="{ref}" s="{style}"><v>{value!r}</v></c>'
    text = escape(_NOT_XML.sub("", value))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _width(values: Sequence[CellValue]) -> float:
    longest = max(
        (max(len(line) for line in str(v).splitlines() or [""]) for v in values if v is not None),
        default=8,
    )
    return float(min(MAX_WIDTH, max(8, longest + 2)))


def write_xlsx(rows: Sequence[Sequence[CellValue]], name: str) -> bytes:
    """The rows as one sheet; the first row is the header."""
    width = max((len(row) for row in rows), default=0)
    columns = [[row[i] if i < len(row) else None for row in rows] for i in range(width)]
    cols = "".join(
        f'<col min="{i + 1}" max="{i + 1}" width="{_width(values)}" customWidth="1"/>'
        for i, values in enumerate(columns)
    )
    body = "".join(
        f'<row r="{r + 1}">'
        + "".join(
            _cell(f"{column_letter(c)}{r + 1}", value, 1 if r == 0 else 0)
            for c, value in enumerate(row)
        )
        + "</row>"
        for r, row in enumerate(rows)
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>"
        + (f"<cols>{cols}</cols>" if cols else "")
        + f"<sheetData>{body}</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name(name), {chr(34): "&quot;"})}" sheetId="1" '
        'r:id="rId1"/></sheets></workbook>'
    )
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", _CONTENT_TYPES)
        package.writestr("_rels/.rels", _ROOT_RELS)
        package.writestr("xl/workbook.xml", workbook)
        package.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        package.writestr("xl/styles.xml", _STYLES)
        package.writestr("xl/worksheets/sheet1.xml", sheet)
    return out.getvalue()
