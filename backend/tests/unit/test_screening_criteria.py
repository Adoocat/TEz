"""Task 25: screening criteria — codes, stages, order (1-9 shortcuts) and archiving."""

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
from tez.modules.reviews import service
from tez.modules.reviews.models import Decision, RecordOrigin, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository

TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def review_id(client: TestClient) -> str:
    return client.post("/reviews", json={"title": "SLR"}).json()["id"]


def add(client: TestClient, review_id: str, **body: object) -> dict[str, Any]:
    response = client.post(f"/reviews/{review_id}/criteria", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def listed(client: TestClient, review_id: str) -> list[dict[str, Any]]:
    return client.get(f"/reviews/{review_id}/criteria").json()


def test_codes_follow_the_kind_unless_given(client: TestClient, review_id: str) -> None:
    i1 = add(client, review_id, kind="inclusion", text="Empirical study")
    e1 = add(client, review_id, kind="exclusion", text="  Not in English  ")
    e2 = add(client, review_id, kind="exclusion", text="No evaluation", stage="full_text")
    own = add(client, review_id, kind="exclusion", code=" e-lang ", text="Language")

    assert [i1["code"], e1["code"], e2["code"], own["code"]] == ["I1", "E1", "E2", "E-LANG"]
    assert e1["text"] == "Not in English"
    assert i1["stage"] is None  # both stages
    assert e2["stage"] == "full_text"
    assert [c["code"] for c in listed(client, review_id)] == ["I1", "E1", "E2", "E-LANG"]


def test_a_code_is_unique_in_the_review(client: TestClient, review_id: str) -> None:
    add(client, review_id, kind="exclusion", text="One")

    response = client.post(
        f"/reviews/{review_id}/criteria", json={"kind": "inclusion", "code": "e1", "text": "Two"}
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "screening.criterion_code_taken",
        "params": {"code": "E1"},
    }


@pytest.mark.parametrize(
    "body",
    [
        {"kind": "inclusion", "text": "  "},
        {"kind": "maybe", "text": "x"},
        {"kind": "inclusion", "text": "x", "stage": "abstract"},
        {"kind": "inclusion", "text": "x", "code": "with space"},
        {"kind": "inclusion", "text": "x", "code": "C" * 17},
        {"kind": "inclusion", "text": "x", "extra": 1},
    ],
)
def test_an_invalid_criterion_is_rejected(
    client: TestClient, review_id: str, body: dict[str, object]
) -> None:
    assert client.post(f"/reviews/{review_id}/criteria", json=body).status_code == 422


def test_shortcuts_are_per_stage_and_follow_the_order(client: TestClient, review_id: str) -> None:
    both = add(client, review_id, kind="inclusion", text="Both stages")
    ta = add(client, review_id, kind="exclusion", text="Title only", stage="title_abstract")
    ft = add(client, review_id, kind="exclusion", text="Full text only", stage="full_text")

    shortcuts = {c["code"]: c["shortcuts"] for c in listed(client, review_id)}
    assert shortcuts == {
        "I1": {"title_abstract": 1, "full_text": 1},
        "E1": {"title_abstract": 2, "full_text": None},
        "E2": {"title_abstract": None, "full_text": 2},
    }

    response = client.put(
        f"/reviews/{review_id}/criteria/order",
        json={"criterion_ids": [ft["id"], ta["id"], both["id"]]},
    )

    assert response.status_code == 200, response.text
    assert [c["code"] for c in response.json()] == ["E2", "E1", "I1"]
    shortcuts = {c["code"]: c["shortcuts"] for c in listed(client, review_id)}
    assert shortcuts == {
        "E2": {"title_abstract": None, "full_text": 1},
        "E1": {"title_abstract": 1, "full_text": None},
        "I1": {"title_abstract": 2, "full_text": 2},
    }


def test_only_the_first_nine_get_a_shortcut(client: TestClient, review_id: str) -> None:
    for n in range(11):
        add(client, review_id, kind="exclusion", text=f"Reason {n}")

    keys = [c["shortcuts"]["title_abstract"] for c in listed(client, review_id)]

    assert keys == [1, 2, 3, 4, 5, 6, 7, 8, 9, None, None]


def test_the_order_must_name_every_active_criterion_once(
    client: TestClient, review_id: str
) -> None:
    a = add(client, review_id, kind="inclusion", text="A")
    add(client, review_id, kind="inclusion", text="B")

    for ids in ([a["id"]], [a["id"], a["id"]], [a["id"], "nope"]):
        response = client.put(f"/reviews/{review_id}/criteria/order", json={"criterion_ids": ids})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "screening.criteria_order_mismatch"


def test_a_criterion_can_be_edited(client: TestClient, review_id: str) -> None:
    criterion = add(client, review_id, kind="exclusion", text="Old", stage="full_text")
    url = f"/reviews/{review_id}/criteria/{criterion['id']}"

    edited = client.patch(url, json={"text": "New", "code": "E9", "stage": None})

    assert edited.status_code == 200, edited.text
    assert edited.json() | {"id": None} == criterion | {
        "id": None,
        "text": "New",
        "code": "E9",
        "stage": None,
        "shortcuts": {"title_abstract": 1, "full_text": 1},
    }
    # Leaving a field out keeps it.
    assert client.patch(url, json={"text": "Newer"}).json()["code"] == "E9"


def _decide_with(library: Library, review_id: str, criterion_id: str) -> None:
    with library.db.write_session() as session:
        repository = ReviewsRepository(session)
        paper_id = LibraryRepository(session).add_paper("P").id
        repository.add_record(review_id, paper_id, RecordOrigin.DATABASE)
        repository.decide(review_id, paper_id, TA, Decision.EXCLUDE, criterion_id=criterion_id)


def test_an_unused_criterion_is_deleted(client: TestClient, review_id: str) -> None:
    criterion = add(client, review_id, kind="exclusion", text="Unused")

    response = client.delete(f"/reviews/{review_id}/criteria/{criterion['id']}")

    assert response.status_code == 204
    assert listed(client, review_id) == []


def test_a_used_criterion_is_archived_not_deleted(
    client: TestClient, library: Library, review_id: str
) -> None:
    used = add(client, review_id, kind="exclusion", text="Used")
    other = add(client, review_id, kind="exclusion", text="Other")
    _decide_with(library, review_id, str(used["id"]))
    url = f"/reviews/{review_id}/criteria/{used['id']}"

    refused = client.delete(url)

    assert refused.status_code == 409
    assert refused.json()["error"] == {
        "code": "screening.criterion_in_use",
        "params": {"criterion_id": used["id"]},
    }
    assert listed(client, review_id)[0]["used"] is True

    archived = client.patch(url, json={"archived": True}).json()

    assert archived["archived"] is True
    assert archived["shortcuts"] == {"title_abstract": None, "full_text": None}
    # The next criterion moves up to key 1; the archived one stays listed, last.
    rows = listed(client, review_id)
    assert [(c["code"], c["shortcuts"]["title_abstract"]) for c in rows] == [
        ("E2", 1),
        ("E1", None),
    ]
    assert rows[0]["id"] == other["id"]
    # An archived criterion is left out of the order.
    order = client.put(
        f"/reviews/{review_id}/criteria/order", json={"criterion_ids": [other["id"]]}
    )
    assert order.status_code == 200

    restored = client.patch(url, json={"archived": False}).json()
    assert restored["archived"] is False
    assert restored["shortcuts"]["title_abstract"] == 2


def test_the_kind_of_a_used_criterion_cannot_change(
    client: TestClient, library: Library, review_id: str
) -> None:
    used = add(client, review_id, kind="exclusion", text="Used")
    _decide_with(library, review_id, str(used["id"]))

    response = client.patch(
        f"/reviews/{review_id}/criteria/{used['id']}", json={"kind": "inclusion"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "screening.criterion_in_use"


def test_criteria_of_another_review_or_unknown_ones_are_not_found(
    client: TestClient, review_id: str
) -> None:
    other_review = client.post("/reviews", json={"title": "Other"}).json()["id"]
    criterion = add(client, other_review, kind="inclusion", text="Elsewhere")

    for method, path in (
        ("PATCH", f"/reviews/{review_id}/criteria/{criterion['id']}"),
        ("DELETE", f"/reviews/{review_id}/criteria/nope"),
    ):
        response = client.request(method, path, json={"text": "x"} if method == "PATCH" else None)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "screening.criterion_not_found"
    assert client.get("/reviews/nope/criteria").json()["error"]["code"] == "review.not_found"


def test_the_screening_service_reads_a_stage_s_criteria_in_key_order(
    client: TestClient, library: Library, review_id: str
) -> None:
    add(client, review_id, kind="inclusion", text="Both")
    add(client, review_id, kind="exclusion", text="Full text only", stage="full_text")
    archived = add(client, review_id, kind="exclusion", text="Gone")
    add(client, review_id, kind="exclusion", text="Title only", stage="title_abstract")
    client.patch(f"/reviews/{review_id}/criteria/{archived['id']}", json={"archived": True})

    title_abstract = service.criteria_for_stage(library.db, review_id, TA)
    full_text = service.criteria_for_stage(library.db, review_id, FT)

    assert [(c.code, c.shortcut) for c in title_abstract] == [("I1", 1), ("E3", 2)]
    assert [(c.code, c.shortcut) for c in full_text] == [("I1", 1), ("E1", 2)]


# --- highlight keywords (Task 32, ADR 0023) ---------------------------------------------


def test_a_criterion_keeps_its_highlight_keywords_once_each(
    client: TestClient, review_id: str
) -> None:
    made = add(
        client,
        review_id,
        kind="inclusion",
        text="Code review",
        keywords=[" code review ", "Işık", "ışık", "IŞIK", "LLM"],
    )
    assert made["keywords"] == ["code review", "Işık", "LLM"]

    changed = client.patch(
        f"/reviews/{review_id}/criteria/{made['id']}", json={"keywords": ["review"]}
    ).json()
    untouched = client.patch(
        f"/reviews/{review_id}/criteria/{made['id']}", json={"text": "Code reviews"}
    ).json()

    assert changed["keywords"] == ["review"]
    assert untouched["keywords"] == ["review"]
    stage = client.get(f"/reviews/{review_id}/screening/title_abstract/criteria").json()
    assert [(c["code"], c["shortcut"], c["keywords"]) for c in stage] == [("I1", 1, ["review"])]


@pytest.mark.parametrize("keywords", [[""], ["x" * 101], ["k"] * 51])
def test_invalid_keywords_are_rejected(
    client: TestClient, review_id: str, keywords: list[str]
) -> None:
    response = client.post(
        f"/reviews/{review_id}/criteria",
        json={"kind": "exclusion", "text": "Off topic", "keywords": keywords},
    )
    assert response.status_code == 422
