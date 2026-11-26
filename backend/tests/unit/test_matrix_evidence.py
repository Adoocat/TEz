"""Task 53: passages of a paper's PDF linked to its matrix cells.

Acceptance (with the reader, in E2E): cell -> PDF sentence -> cell. Here: linking checks the
passage is the row's paper's, keeps the cell while a passage rests on it, and the matrix says
how much of its content rests on passages.
"""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import make_text_pdf
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.jobs.handlers import registry
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import Decision, RecordOrigin, ReviewMethod, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService
from tez.modules.settings.secrets import MemorySecretStore
from tez.worker import Worker

RECT = [[72.0, 700.0, 300.0, 712.0]]
PAGE_1 = ["Methods of the study", "We interviewed forty-two participants", "in twelve schools."]
PAGE_2 = ["Results follow here", "Participants described the workload", "as their main concern."]


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def error(response: Any, status: int) -> str:
    assert response.status_code == status, response.text
    return response.json()["error"]["code"]


class Setup:
    """Two papers with a PDF each, both included at full text, and a matrix."""

    def __init__(self, client: TestClient, library: Library) -> None:
        self.client = client
        self.files: list[str] = []
        self.papers: list[str] = []
        for name, extra in (("first.pdf", "One"), ("second.pdf", "Two")):
            pdf = make_text_pdf([PAGE_1, [*PAGE_2, f"Paper {extra}."]])
            made = ok(client.post("/pdfs", params={"file_name": name}, content=pdf), 201)
            self.files.append(made["attachment_id"])
            self.papers.append(ok(client.get(f"/attachments/{made['attachment_id']}"))["paper_id"])
        worker = Worker(library.db, registry, lease=timedelta(seconds=30))
        while worker.run_once():
            pass
        with library.db.write_session() as session:
            reviews = ReviewsRepository(session)
            self.review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
            screening = ScreeningService(session)
            for paper in self.papers:
                reviews.add_record(self.review, paper, RecordOrigin.DATABASE)
                for stage in (ScreeningStage.TITLE_ABSTRACT, ScreeningStage.FULL_TEXT):
                    screening.decide(self.review, paper, stage, Decision.INCLUDE)
        self.matrix = ok(client.post(f"/reviews/{self.review}/matrices", json={"name": "M"}), 201)[
            "id"
        ]
        self.findings = self.column("Findings")
        self.size = self.column("Sample", "number")

    def column(self, name: str, data_type: str = "text") -> str:
        body = {"name": name, "data_type": data_type}
        return ok(self.client.post(f"/matrices/{self.matrix}/columns", json=body), 201)["id"]

    def anchor(self, file: int, page: int, quote: str) -> str:
        made = ok(
            self.client.post(
                f"/attachments/{self.files[file]}/anchors",
                json={"page": page, "rects": RECT, "quote": quote},
            ),
            201,
        )
        assert made["status"] == "verified"
        return made["id"]

    def cell_path(self, paper: int, column: str) -> str:
        return f"/matrices/{self.matrix}/cells/{self.papers[paper]}/{column}"

    def link(self, paper: int, column: str, anchor: str, fill: bool = False) -> Any:
        return self.client.post(
            f"{self.cell_path(paper, column)}/evidence", json={"anchor_id": anchor, "fill": fill}
        )

    def view(self) -> dict[str, Any]:
        return ok(self.client.get(f"/matrices/{self.matrix}"))

    def cell(self, paper: int, column: str) -> dict[str, Any] | None:
        row = next(r for r in self.view()["rows"] if r["paper_id"] == self.papers[paper])
        return next((c for c in row["cells"] if c["column_id"] == column), None)


@pytest.fixture
def setup(client: TestClient, library: Library) -> Setup:
    return Setup(client, library)


def test_a_passage_fills_an_empty_text_cell_and_is_shown_with_it(setup: Setup) -> None:
    quote = setup.anchor(0, 2, "Participants described the workload")
    cell = ok(setup.link(0, setup.findings, quote, fill=True), 201)
    assert cell["value"] == "Participants described the workload"
    assert [(e["anchor_id"], e["page"], e["status"]) for e in cell["evidence"]] == [
        (quote, 2, "verified")
    ]
    assert cell["evidence"][0]["attachment_id"] == setup.files[0]
    assert setup.cell(0, setup.findings) == cell

    # A second passage is added, the value stays; the same one again changes nothing.
    other = setup.anchor(0, 1, "We interviewed forty-two participants")
    twice = ok(setup.link(0, setup.findings, other, fill=True), 201)
    assert twice["value"] == "Participants described the workload"
    assert [e["anchor_id"] for e in twice["evidence"]] == [quote, other]
    again = ok(setup.link(0, setup.findings, other), 201)
    assert len(again["evidence"]) == 2


def test_a_passage_must_be_the_rows_paper(setup: Setup) -> None:
    from_other_paper = setup.anchor(1, 1, "We interviewed forty-two participants")
    assert error(setup.link(0, setup.findings, from_other_paper), 400) == (
        "matrix.evidence_other_paper"
    )
    assert error(setup.link(0, setup.findings, "nope"), 404) == "anchor.not_found"


def test_a_cell_with_a_passage_stays_until_the_passage_goes(setup: Setup) -> None:
    passage = setup.anchor(0, 1, "We interviewed forty-two participants")
    ok(setup.client.put(setup.cell_path(0, setup.size), json={"value": 42}))
    ok(setup.link(0, setup.size, passage), 201)

    # Clearing the value keeps the passage.
    cleared = ok(setup.client.put(setup.cell_path(0, setup.size), json={"value": None}))
    assert cleared["value"] is None and len(cleared["evidence"]) == 1
    # So does a type change that leaves it empty.
    ok(
        setup.client.put(
            f"/matrices/{setup.matrix}/columns/{setup.size}/type", json={"data_type": "text"}
        )
    )
    assert setup.cell(0, setup.size) is not None

    # Taking the passage off an empty cell removes the cell; the anchor stays.
    gone = setup.client.delete(f"{setup.cell_path(0, setup.size)}/evidence/{passage}")
    assert ok(gone) is None
    assert setup.cell(0, setup.size) is None
    assert ok(setup.client.get(f"/anchors/{passage}"))["id"] == passage
    again = setup.client.delete(f"{setup.cell_path(0, setup.size)}/evidence/{passage}")
    assert error(again, 404) == "matrix.evidence_not_found"


def test_coverage_counts_filled_cells_that_rest_on_a_passage(setup: Setup) -> None:
    assert setup.view()["coverage"] == {"filled": 0, "sourced": 0, "rows": 0, "rows_sourced": 0}
    ok(setup.link(0, setup.findings, setup.anchor(0, 2, "as their main concern"), fill=True), 201)
    ok(setup.client.put(setup.cell_path(0, setup.size), json={"value": 42}))
    ok(setup.client.put(setup.cell_path(1, setup.findings), json={"value": "Workload"}))
    ok(setup.link(1, setup.findings, setup.anchor(1, 2, "as their main concern")), 201)
    # Three filled cells, two with a passage; one of two rows rests wholly on passages.
    assert setup.view()["coverage"] == {"filled": 3, "sourced": 2, "rows": 2, "rows_sourced": 1}


def test_the_reader_lists_the_papers_cells(setup: Setup, client: TestClient) -> None:
    ok(setup.link(0, setup.findings, setup.anchor(0, 2, "as their main concern"), fill=True), 201)
    listed = ok(client.get(f"/papers/{setup.papers[0]}/matrices"))
    assert [(m["matrix_id"], m["matrix_name"]) for m in listed] == [(setup.matrix, "M")]
    assert [c["name"] for c in listed[0]["columns"]] == ["Findings", "Sample"]
    assert [c["value"] for c in listed[0]["cells"]] == ["as their main concern"]
    # The other paper is a row with no cells yet; a paper not in the review is in no matrix.
    assert ok(client.get(f"/papers/{setup.papers[1]}/matrices"))[0]["cells"] == []
    assert ok(client.get("/papers/nope/matrices")) == []
