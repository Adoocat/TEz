"""Task 54: the matrix as CSV, Excel and Markdown, with passages and pages.

Acceptance: Turkish letters are right in Excel. The .xlsx is read back cell by cell; the CSV
starts with the byte order mark Excel needs to read UTF-8.
"""

import base64
import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.matrix import export
from tez.modules.matrix.schemas import (
    CellView,
    ColumnView,
    Coverage,
    EvidenceView,
    ExportLabels,
    MatrixView,
    OptionView,
    RowView,
)
from tez.modules.reviews.models import Decision, RecordOrigin, ReviewMethod, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService
from tez.shared.xlsx import column_letter, sheet_name, write_xlsx

MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TURKISH = "Işık, ğüşöç İĞÜŞÖÇ ı"
LABELS = ExportLabels(
    paper="Makale",
    title="Başlık",
    year="Yıl",
    quality="Kalite",
    evidence="Kanıt",
    page="s.",
    et_al="vd.",
    yes="Evet",
    no="Hayır",
)


def read_xlsx(data: bytes) -> list[list[str]]:
    """The sheet's cells as text, row by row, the way Excel reads them."""
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        assert package.testzip() is None
        sheet = ElementTree.fromstring(package.read("xl/worksheets/sheet1.xml"))
        ElementTree.fromstring(package.read("[Content_Types].xml"))
    rows: list[list[str]] = []
    for row in sheet.iter(f"{MAIN}row"):
        line: list[str] = []
        for cell in row.iter(f"{MAIN}c"):
            text = cell.find(f"{MAIN}is/{MAIN}t")
            value = cell.find(f"{MAIN}v")
            source = text if text is not None else value
            line.append(source.text or "" if source is not None else "")
        rows.append(line)
    return rows


def cell(column: str, value: Any, *evidence: tuple[str, int], kept: str | None = None) -> CellView:
    return CellView(
        column_id=column,
        value=value,
        kept_text=kept,
        origin="manual",  # type: ignore[arg-type]
        updated_at="2026-11-27T10:00:00Z",  # type: ignore[arg-type]
        evidence=[
            EvidenceView(
                anchor_id=f"a{n}", attachment_id="f", page=page, quote=q, status="verified"
            )
            for n, (q, page) in enumerate(evidence)
        ],
    )


def matrix() -> MatrixView:
    columns = [
        ColumnView(
            id="m",
            name="Yöntem",
            instruction=None,
            data_type="multi_enum",  # type: ignore[arg-type]
            options=[OptionView(id="s", label="Anket"), OptionView(id="g", label="Görüşme")],
            sort_order=0,
        ),
        ColumnView(
            id="n",
            name="Örneklem",
            instruction=None,
            data_type="number",  # type: ignore[arg-type]
            options=[],
            sort_order=1,
        ),
        ColumnView(
            id="o",
            name="Açık erişim",
            instruction=None,
            data_type="bool",  # type: ignore[arg-type]
            options=[],
            sort_order=2,
        ),
    ]
    row = {"venue": None, "reading_status": "read", "included": True}
    rows = [
        RowView(
            paper_id="p1",
            title=f"Öğretmenlerin {TURKISH} | deneyimi",
            year=2024,
            first_author="Ayşe Yılmaz",
            author_count=2,
            cells=[
                cell("m", ["s", "g"], ("Katılımcılarla görüşüldü", 4)),
                cell("n", 42),
                cell("o", False),
            ],
            **row,  # type: ignore[arg-type]
        ),
        RowView(
            paper_id="p2",
            title="Second",
            year=None,
            first_author=None,
            author_count=0,
            cells=[cell("n", None, kept="yaklaşık 30")],
            **row,  # type: ignore[arg-type]
        ),
        RowView(
            paper_id="p3",
            title="Excluded later",
            year=2020,
            first_author="Kim",
            author_count=1,
            cells=[cell("n", 7)],
            **{**row, "included": False},  # type: ignore[arg-type]
        ),
    ]
    return MatrixView(
        id="x",
        review_id="r",
        name="Sentez: [Örnek]",
        columns=columns,
        rows=rows,
        coverage=Coverage(filled=0, sourced=0, rows=0, rows_sourced=0),
    )


SCORES = {"p1": export.Score(3, 4)}


def test_excel_keeps_turkish_letters_and_types() -> None:
    found = export.table(matrix(), SCORES, LABELS)
    data = base64.b64decode(export.to_file(matrix(), SCORES, LABELS, "xlsx").content_base64)
    sheet = read_xlsx(data)
    assert sheet[0] == [
        "Makale",
        "Başlık",
        "Yıl",
        "Kalite",
        "Yöntem",
        "Yöntem (Kanıt)",
        "Örneklem",
        "Açık erişim",
    ]
    assert sheet[1] == [
        "Yılmaz vd. 2024",
        f"Öğretmenlerin {TURKISH} | deneyimi",
        "2024",
        "3 / 4",
        "Anket; Görüşme",
        "“Katılımcılarla görüşüldü” (s. 4)",
        "42",
        "Hayır",
    ]
    # Excluded papers are not exported; a value kept as text is.
    assert len(sheet) == 3 and "yaklaşık 30" in sheet[2]
    assert found.rows[0][6] == 42  # a number stays a number
    with zipfile.ZipFile(io.BytesIO(data)) as package:
        workbook = package.read("xl/workbook.xml").decode("utf-8")
        assert 'name="Sentez:  Örnek"' not in workbook and "Sentez" in workbook
        assert '<c r="G2" s="0"><v>42</v></c>' in package.read("xl/worksheets/sheet1.xml").decode()


def test_csv_has_a_byte_order_mark_for_excel() -> None:
    data = base64.b64decode(export.to_file(matrix(), None, LABELS, "csv").content_base64)
    assert data.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
    assert rows[0][:3] == ["Makale", "Başlık", "Yıl"] and "Kalite" not in rows[0]
    assert rows[1][1] == f"Öğretmenlerin {TURKISH} | deneyimi"
    assert rows[2][:3] == ["Second", "Second", ""]


def test_markdown_numbers_the_passages_under_the_table() -> None:
    text = base64.b64decode(export.to_file(matrix(), SCORES, LABELS, "md").content_base64).decode(
        "utf-8"
    )
    lines = text.splitlines()
    assert lines[0] == "# Sentez: [Örnek]"
    assert lines[2] == "| Makale | Başlık | Yıl | Kalite | Yöntem | Örneklem | Açık erişim |"
    assert lines[4] == (
        f"| Yılmaz vd. 2024 | Öğretmenlerin {TURKISH} \\| deneyimi | 2024 | 3 / 4 "
        "| Anket; Görüşme [1] | 42 | Hayır |"
    )
    assert "## Kanıt" in lines
    assert lines[-1] == "1. Yılmaz vd. 2024, Yöntem: “Katılımcılarla görüşüldü” (s. 4)"


def test_xlsx_helpers() -> None:
    assert [column_letter(i) for i in (0, 25, 26, 701, 702)] == ["A", "Z", "AA", "ZZ", "AAA"]
    assert sheet_name("a/b:c*d?[e]" + "x" * 40) == "a b c d  e " + "x" * 20
    assert sheet_name("::") == "Sheet1"
    # Characters XML cannot hold are dropped, not written.
    sheet = read_xlsx(write_xlsx([["a\x00b\x1fc", 1.5, None]], "S"))
    assert sheet == [["abc", "1.5"]]


# --- through the API, with the quality stage -----------------------------------------------


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, Library]]:
    library = open_library(tmp_path / "lib", create=True)
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c, library
    library.close()


def test_export_through_the_api(client: tuple[TestClient, Library]) -> None:
    api, library = client
    with library.db.write_session() as session:
        paper = LibraryRepository(session).add_paper(f"Çalışma {TURKISH}", year=2023).id
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
        reviews.add_record(review, paper, RecordOrigin.DATABASE)
        screening = ScreeningService(session)
        for stage in (ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT):
            screening.decide(review, paper, stage, Decision.INCLUDE)
    made = api.post(f"/reviews/{review}/matrices", json={"name": "Matris"}).json()
    column = api.post(f"/matrices/{made['id']}/columns", json={"name": "Bulgu"}).json()
    api.put(f"/matrices/{made['id']}/cells/{paper}/{column['id']}", json={"value": "Işıklı ortam"})

    # The quality stage is off: no quality column.
    response = api.post(
        f"/matrices/{made['id']}/export",
        json={"format": "xlsx", "labels": LABELS.model_dump()},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mime_type"].endswith("spreadsheetml.sheet")
    sheet = read_xlsx(base64.b64decode(body["content_base64"]))
    assert sheet == [
        ["Makale", "Başlık", "Yıl", "Bulgu"],
        # No author: the title stands in for the citation.
        [f"Çalışma {TURKISH} 2023", f"Çalışma {TURKISH}", "2023", "Işıklı ortam"],
    ]

    api.put(f"/reviews/{review}/quality/setting", json={"enabled": True})
    with_quality = api.post(f"/matrices/{made['id']}/export", json={"format": "csv"}).json()
    rows = list(
        csv.reader(
            io.StringIO(base64.b64decode(with_quality["content_base64"]).decode("utf-8-sig"))
        )
    )
    assert rows[0] == ["Paper", "Title", "Year", "Quality", "Bulgu"]

    # The review panel's stage reads the summary.
    listed = api.get(f"/reviews/{review}/matrices").json()
    assert (listed[0]["rows"], listed[0]["coverage"]["filled"]) == (1, 1)
