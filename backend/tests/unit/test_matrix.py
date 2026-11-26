"""Task 51: the literature matrix through the API.

Acceptance: when a column's type changes, no data is lost without a word; the cells of a paper
that is excluded are kept. Rows are the papers included at full text.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.library.repository import LibraryRepository
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import (
    CriterionKind,
    Decision,
    RecordOrigin,
    ReviewMethod,
    ScreeningStage,
)
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService

TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    library = open_library(tmp_path / "lib", create=True)
    yield library
    library.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


class Review:
    """Three papers included at full text, one only at title-abstract."""

    def __init__(self, library: Library) -> None:
        self.library = library
        with library.db.write_session() as session:
            papers = LibraryRepository(session)
            ids = [papers.add_paper(f"Çalışma {n}", year=2020 + n).id for n in range(4)]
            reviews = ReviewsRepository(session)
            self.id = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
            self.reason = reviews.add_criterion(
                self.id, CriterionKind.EXCLUSION, "E1", "Wrong population"
            ).id
            screening = ScreeningService(session)
            for paper_id in ids:
                reviews.add_record(self.id, paper_id, RecordOrigin.DATABASE)
                screening.decide(self.id, paper_id, TA, Decision.INCLUDE)
            for paper_id in ids[:3]:
                screening.decide(self.id, paper_id, FT, Decision.INCLUDE)
        self.included = ids[:3]
        self.not_included = ids[3]

    def decide(self, paper_id: str, decision: Decision) -> None:
        with self.library.db.write_session() as session:
            reason = self.reason if decision == Decision.EXCLUDE else None
            ScreeningService(session).decide(self.id, paper_id, FT, decision, criterion_id=reason)


@pytest.fixture
def review(library: Library) -> Review:
    return Review(library)


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def error(response: Any, status: int) -> str:
    assert response.status_code == status, response.text
    return response.json()["error"]["code"]


class Grid:
    def __init__(self, client: TestClient, review: Review) -> None:
        self.client = client
        made = ok(client.post(f"/reviews/{review.id}/matrices", json={"name": "Sentez"}), 201)
        self.id = made["id"]
        self.base = f"/matrices/{self.id}"

    def column(self, name: str, data_type: str = "text", **extra: Any) -> dict[str, Any]:
        body = {"name": name, "data_type": data_type, **extra}
        return ok(self.client.post(f"{self.base}/columns", json=body), 201)

    def put(self, paper: str, column: str, value: Any) -> Any:
        return self.client.put(f"{self.base}/cells/{paper}/{column}", json={"value": value})

    def view(self) -> dict[str, Any]:
        return ok(self.client.get(self.base))

    def cells(self, column: str) -> dict[str, tuple[Any, str | None]]:
        """paper id -> (value, kept text) for one column."""
        found: dict[str, tuple[Any, str | None]] = {}
        for row in self.view()["rows"]:
            for cell in row["cells"]:
                if cell["column_id"] == column:
                    found[row["paper_id"]] = (cell["value"], cell["kept_text"])
        return found

    def change(self, column: str, **body: Any) -> dict[str, Any]:
        return ok(self.client.put(f"{self.base}/columns/{column}/type", json=body))


@pytest.fixture
def grid(client: TestClient, review: Review) -> Grid:
    return Grid(client, review)


# --- acceptance ------------------------------------------------------------------------------


def test_a_type_change_loses_nothing_without_a_word(grid: Grid, review: Review) -> None:
    size = grid.column("Örneklem")["id"]
    a, b, c = review.included
    for paper, text in zip(review.included, ["120", "1.420", "yaklaşık 30"], strict=True):
        ok(grid.put(paper, size, text))

    # Asked first: what would happen.
    trial = grid.change(size, data_type="number", dry_run=True)
    assert (trial["applied"], trial["cells"], trial["converted"]) == (False, 3, 1)
    assert {k["paper_id"]: k["text"] for k in trial["kept"]} == {b: "1.420", c: "yaklaşık 30"}
    assert grid.cells(size) == {a: ("120", None), b: ("1.420", None), c: ("yaklaşık 30", None)}

    report = grid.change(size, data_type="number")
    assert report["applied"] is True and report["column"]["data_type"] == "number"
    assert grid.cells(size) == {a: (120, None), b: (None, "1.420"), c: (None, "yaklaşık 30")}

    # Fixing a kept cell is writing a value; back to text, everything is there.
    ok(grid.put(b, size, 1420))
    grid.change(size, data_type="text")
    assert grid.cells(size) == {a: ("120", None), b: ("1420", None), c: ("yaklaşık 30", None)}


def test_an_excluded_papers_cells_are_kept_and_come_back(grid: Grid, review: Review) -> None:
    method = grid.column("Yöntem")["id"]
    paper = review.included[0]
    ok(grid.put(paper, method, "Nitel"))

    review.decide(paper, Decision.EXCLUDE)
    rows = {row["paper_id"]: row for row in grid.view()["rows"]}
    assert [r["paper_id"] for r in grid.view()["rows"] if r["included"]] == review.included[1:]
    assert rows[paper]["included"] is False
    assert rows[paper]["cells"][0]["value"] == "Nitel"
    # Hidden cells are kept, not edited: the paper is out of the review.
    assert error(grid.put(paper, method, "Nicel"), 409) == "matrix.paper_not_included"

    review.decide(paper, Decision.INCLUDE)
    rows = {row["paper_id"]: row for row in grid.view()["rows"]}
    assert rows[paper]["included"] is True
    assert rows[paper]["cells"][0]["value"] == "Nitel"


# --- rows, columns, cells --------------------------------------------------------------------


def test_rows_are_the_papers_included_at_full_text(grid: Grid, review: Review) -> None:
    view = grid.view()
    assert [row["paper_id"] for row in view["rows"]] == review.included
    first = view["rows"][0]
    assert (first["title"], first["year"], first["reading_status"]) == ("Çalışma 0", 2020, "unread")
    assert error(grid.put(review.not_included, grid.column("X")["id"], "a"), 409) == (
        "matrix.paper_not_included"
    )


def test_each_type_checks_its_values(grid: Grid, review: Review) -> None:
    paper = review.included[0]
    number = grid.column("n", "number")["id"]
    yes_no = grid.column("Açık erişim", "bool")["id"]
    method = grid.column("Yöntem", "multi_enum", options=[{"label": "Anket"}, {"label": "Görüşme"}])
    survey, interview = (option["id"] for option in method["options"])

    assert ok(grid.put(paper, number, 30.0))["value"] == 30
    assert ok(grid.put(paper, yes_no, True))["value"] is True
    assert ok(grid.put(paper, method["id"], [interview, survey]))["value"] == [survey, interview]
    assert error(grid.put(paper, number, "30"), 400) == "matrix.value_invalid"
    assert error(grid.put(paper, method["id"], ["nope"]), 400) == "matrix.value_invalid"

    # Null clears a cell.
    assert ok(grid.put(paper, number, None)) is None
    assert number not in grid.cells(number) and grid.cells(number) == {}


def test_text_becomes_choices_found_in_the_cells(grid: Grid, review: Review) -> None:
    column = grid.column("Desen")["id"]
    a, b, c = review.included
    ok(grid.put(a, column, "Anket"))
    ok(grid.put(b, column, "anket; Görüşme"))
    ok(grid.put(c, column, "Görüşme"))

    report = grid.change(column, data_type="multi_enum")
    labels = {o["label"]: o["id"] for o in report["column"]["options"]}
    assert list(labels) == ["Anket", "Görüşme"] and report["kept"] == []
    survey, interview = labels["Anket"], labels["Görüşme"]
    assert grid.cells(column) == {
        a: ([survey], None),
        b: ([survey, interview], None),
        c: ([interview], None),
    }

    # To a single choice: the cell with two keeps them as text.
    report = grid.change(column, data_type="enum")
    assert report["kept"] == [{"paper_id": b, "text": "Anket; Görüşme"}]
    assert grid.cells(column)[b] == (None, "Anket; Görüşme")


def test_options_renamed_and_removed(grid: Grid, review: Review) -> None:
    made = grid.column("Desen", "enum", options=[{"label": "Anket"}, {"label": "Deney"}])
    survey, trial = (o["id"] for o in made["options"])
    a, b, _ = review.included
    ok(grid.put(a, made["id"], survey))
    ok(grid.put(b, made["id"], trial))

    report = grid.change(made["id"], data_type="enum", options=[{"id": survey, "label": "Survey"}])
    assert report["kept"] == [{"paper_id": b, "text": "Deney"}]
    assert grid.cells(made["id"]) == {a: (survey, None), b: (None, "Deney")}

    # The option comes back under a new id: the kept text is read again.
    report = grid.change(
        made["id"],
        data_type="enum",
        options=[{"id": survey, "label": "Survey"}, {"label": "deney"}],
    )
    again = report["column"]["options"][1]["id"]
    assert report["kept"] == [] and grid.cells(made["id"])[b] == (again, None)

    unknown = grid.client.put(
        f"{grid.base}/columns/{made['id']}/type",
        json={"data_type": "enum", "options": [{"id": "nope", "label": "X"}]},
    )
    assert error(unknown, 400) == "matrix.option_unknown"


def test_yes_no_to_text_in_the_users_words(grid: Grid, review: Review) -> None:
    column = grid.column("Açık erişim", "bool")["id"]
    ok(grid.put(review.included[0], column, False))
    grid.change(column, data_type="text", true_text="Evet", false_text="Hayır")
    assert grid.cells(column) == {review.included[0]: ("Hayır", None)}


def test_columns_are_named_explained_ordered_and_deleted(grid: Grid, review: Review) -> None:
    first = grid.column("Yöntem", instruction="Araştırma deseni")["id"]
    second = grid.column("Bulgular")["id"]
    renamed = ok(
        grid.client.patch(f"{grid.base}/columns/{first}", json={"name": "Desen", "instruction": ""})
    )
    assert (renamed["name"], renamed["instruction"]) == ("Desen", None)

    order = ok(grid.client.put(f"{grid.base}/columns/order", json={"column_ids": [second, first]}))
    assert [c["id"] for c in order] == [second, first]
    wrong = grid.client.put(f"{grid.base}/columns/order", json={"column_ids": [second]})
    assert error(wrong, 400) == "matrix.order_mismatch"

    ok(grid.put(review.included[0], first, "Nitel"))
    assert grid.client.delete(f"{grid.base}/columns/{first}").status_code == 204
    assert [c["id"] for c in grid.view()["columns"]] == [second]
    assert grid.view()["rows"][0]["cells"] == []


def test_matrices_of_a_review(client: TestClient, review: Review, grid: Grid) -> None:
    grid.column("Yöntem")
    listed = ok(client.get(f"/reviews/{review.id}/matrices"))
    assert [(m["name"], m["columns"]) for m in listed] == [("Sentez", 1)]
    assert ok(client.patch(grid.base, json={"name": "Matris"}))["name"] == "Matris"
    assert client.delete(grid.base).status_code == 204
    assert error(client.get(grid.base), 404) == "matrix.not_found"
    assert error(client.get("/reviews/nope/matrices"), 404) == "review.not_found"
