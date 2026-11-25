"""Task 46 acceptance: when a PDF changes its quotes are found again; one that is not there is
marked lost, and never moved to a place that only looks right."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tests.pdfs import broken_pdf, make_pdf, make_text_pdf
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.anchors.boxes import merge_lines, passage_rects
from tez.modules.fulltext.extraction import extract_pages
from tez.modules.jobs.handlers import registry
from tez.modules.library.service import Library, open_library
from tez.modules.settings.secrets import MemorySecretStore
from tez.shared.passages import Quote, key_of, locate_on_page, relocate
from tez.worker import Worker

RECT = [[72.0, 700.0, 300.0, 715.0]]


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


def run_jobs(library: Library) -> None:
    worker = Worker(library.db, registry, lease=timedelta(seconds=30))
    while worker.run_once():
        pass


def upload(client: TestClient, library: Library, data: bytes, name: str = "paper.pdf") -> str:
    response = client.post("/pdfs", params={"file_name": name}, content=data)
    assert response.status_code == 201, response.text
    run_jobs(library)
    return response.json()["attachment_id"]


def replace(client: TestClient, library: Library, attachment: str, data: bytes) -> dict[str, Any]:
    response = client.put(
        f"/attachments/{attachment}/file", params={"file_name": "v2.pdf"}, content=data
    )
    assert response.status_code == 200, response.text
    run_jobs(library)
    return response.json()


def anchor(client: TestClient, attachment: str, **body: object) -> dict[str, Any]:
    response = client.post(
        f"/attachments/{attachment}/anchors", json={"page": 1, "rects": RECT, **body}
    )
    assert response.status_code == 201, response.text
    return response.json()


def get(client: TestClient, anchor_id: str) -> dict[str, Any]:
    return client.get(f"/anchors/{anchor_id}").json()


PAGE_1 = ["Methods of the study", "We interviewed forty-two participants", "in twelve schools."]
PAGE_2 = ["Results follow here", "Participants described the workload", "as their main concern."]


def test_an_anchor_is_verified_against_the_files_own_text(
    client: TestClient, library: Library
) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1, PAGE_2]))

    made = anchor(client, attachment, page=2, quote="participants  DESCRIBED the\nwork-load as")

    assert made["status"] == "verified"
    # The words as the file has them, with what stands around them.
    assert made["quote"] == "Participants described the workload as"
    assert made["prefix"].endswith("Results follow here")
    assert made["suffix"].startswith("their main concern")
    assert (made["page"], made["rects"]) == (2, RECT)
    assert made["paper"]["title"] == "paper"
    assert client.get(f"/attachments/{attachment}/anchors").json() == [made]
    assert get(client, made["id"]) == made


def test_the_same_passage_is_the_same_anchor(client: TestClient, library: Library) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1]))

    first = anchor(client, attachment, quote="forty-two participants")
    second = anchor(client, attachment, quote="FORTY-TWO participants")
    other = anchor(client, attachment, quote="twelve schools")

    assert first["id"] == second["id"] != other["id"]


def test_repeats_are_told_apart_by_context_then_by_order(
    client: TestClient, library: Library
) -> None:
    lines = ["alpha the same words beta", "gamma the same words delta", "the same words"]
    attachment = upload(client, library, make_text_pdf([lines]))

    by_context = anchor(
        client, attachment, quote="the same words", prefix="gamma ", suffix=" delta"
    )
    by_order = anchor(client, attachment, quote="the same words", occurrence=2)

    assert by_context["suffix"].startswith("delta")
    assert by_order["prefix"].endswith("delta")


def test_a_quote_that_is_not_in_the_text_stays_unverified(
    client: TestClient, library: Library
) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1]))

    made = anchor(client, attachment, quote="something else entirely")

    assert (made["status"], made["quote"]) == ("unverified", "something else entirely")


def test_a_quote_selected_before_the_text_was_read_is_checked_afterwards(
    client: TestClient, library: Library
) -> None:
    data = make_text_pdf([PAGE_1])
    attachment = client.post("/pdfs", params={"file_name": "p.pdf"}, content=data).json()[
        "attachment_id"
    ]
    made = anchor(client, attachment, quote="interviewed forty-two")
    assert made["status"] == "unverified"

    run_jobs(library)

    assert get(client, made["id"])["status"] == "verified"


def test_an_area_needs_no_text(client: TestClient, library: Library) -> None:
    attachment = upload(client, library, make_pdf(2, text=None))

    made = anchor(client, attachment, kind="area", page=2)

    assert (made["kind"], made["status"], made["quote"]) == ("area", "verified", "")


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"page": 9, "quote": "x"}, "anchor.no_such_page"),
        ({"page": 0, "quote": "x"}, "request.invalid"),
        ({"quote": "   "}, "request.invalid"),
        ({"quote": "x", "rects": []}, "request.invalid"),
        ({"quote": "x", "rects": [[1, 2, 3]]}, "request.invalid"),
    ],
)
def test_bad_anchors_are_refused(
    client: TestClient, library: Library, body: dict[str, object], code: str
) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1]))

    response = client.post(
        f"/attachments/{attachment}/anchors", json={"page": 1, "rects": RECT, **body}
    )

    assert response.status_code == 422
    if code != "request.invalid":
        assert response.json()["error"]["code"] == code
    assert client.get("/anchors/nope").json()["error"]["code"] == "anchor.not_found"


# --- the file changes ------------------------------------------------------------------


def test_a_quote_is_found_again_on_another_page_with_new_boxes(
    client: TestClient, library: Library
) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1, PAGE_2]))
    made = anchor(client, attachment, page=2, quote="Participants described the workload")
    new = [["A new cover page"], ["Another page", *PAGE_1], ["More text", "and more", *PAGE_2]]

    view = replace(client, library, attachment, make_text_pdf(new))

    assert view["id"] == attachment
    moved = get(client, made["id"])
    assert (moved["status"], moved["page"]) == ("verified", 3)
    assert moved["quote"] == "Participants described the workload"
    # The box of line 4 in the new file: one line, 14 points below line 3 (tests/pdfs.py).
    (left, bottom, right, top) = moved["rects"][0]
    assert len(moved["rects"]) == 1
    assert left == pytest.approx(72, abs=2)
    assert right == pytest.approx(72 + 35 * 6.6, abs=3)
    assert bottom <= 720 - 3 * 14 <= top


def test_a_changed_word_still_finds_a_long_quote_but_not_a_short_one(
    client: TestClient, library: Library
) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_2]))
    long = anchor(
        client, attachment, quote="Participants described the workload as their main concern"
    )
    short = anchor(client, attachment, quote="Results follow")
    new = ["Outcomes", "Participants described the workloads", "as their main concern."]

    replace(client, library, attachment, make_text_pdf([["cover"], new]))

    found = get(client, long["id"])
    assert (found["status"], found["page"]) == ("verified", 2)
    assert found["quote"] == "Participants described the workloads as their main concern"
    assert get(client, short["id"])["status"] == "lost"


def test_a_quote_that_is_gone_is_lost_and_keeps_its_words(
    client: TestClient, library: Library
) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1]))
    made = anchor(client, attachment, quote="We interviewed forty-two participants")

    replace(client, library, attachment, make_text_pdf([["Completely different text here"]]))

    lost = get(client, made["id"])
    assert (lost["status"], lost["quote"], lost["page"]) == (
        "lost",
        "We interviewed forty-two participants",
        1,
    )


def test_a_short_quote_does_not_jump_to_the_same_words_elsewhere(
    client: TestClient, library: Library
) -> None:
    attachment = upload(client, library, make_text_pdf([["In this study the sample was small."]]))
    made = anchor(client, attachment, quote="the sample")
    new = [["Unrelated opening"], ["They tasted the sample of cheese."]]

    replace(client, library, attachment, make_text_pdf(new))

    assert get(client, made["id"])["status"] == "lost"


def test_an_area_is_lost_when_the_file_changes_and_back_with_the_old_file(
    client: TestClient, library: Library
) -> None:
    old = make_text_pdf([PAGE_1])
    attachment = upload(client, library, old)
    area = anchor(client, attachment, kind="area")
    text = anchor(client, attachment, quote="twelve schools")

    replace(client, library, attachment, make_text_pdf([["Nothing of it"]]))
    assert get(client, area["id"])["status"] == "lost"
    assert get(client, text["id"])["status"] == "lost"

    replace(client, library, attachment, old)
    assert get(client, area["id"])["status"] == "verified"
    assert get(client, text["id"])["status"] == "verified"


def test_until_the_new_file_is_read_anchors_say_so(client: TestClient, library: Library) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1]))
    made = anchor(client, attachment, quote="twelve schools")

    client.put(
        f"/attachments/{attachment}/file",
        params={"file_name": "v2.pdf"},
        content=make_text_pdf([["x"], PAGE_1]),
    )

    assert get(client, made["id"])["status"] == "checking"
    # The old text is not searched for the new file.
    found = client.get(f"/attachments/{attachment}/find", params={"q": "twelve"}).json()
    assert found["text"] == "pending"
    run_jobs(library)
    assert get(client, made["id"])["status"] == "verified"


def test_a_broken_new_file_leaves_anchors_waiting(client: TestClient, library: Library) -> None:
    attachment = upload(client, library, make_text_pdf([PAGE_1]))
    made = anchor(client, attachment, quote="twelve schools")

    replace(client, library, attachment, broken_pdf())

    assert client.get(f"/attachments/{attachment}").json()["text_status"] == "failed"
    assert get(client, made["id"])["status"] == "checking"


def test_replacing_with_a_file_already_in_the_library_is_refused(
    client: TestClient, library: Library
) -> None:
    one, two = make_text_pdf([["one"]]), make_text_pdf([["two"]])
    first = upload(client, library, one, "one.pdf")
    upload(client, library, two, "two.pdf")

    response = client.put(
        f"/attachments/{first}/file", params={"file_name": "two.pdf"}, content=two
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "attachment.file_in_use"
    # The same file again changes nothing; something else is not a PDF.
    same = client.put(f"/attachments/{first}/file", params={"file_name": "x.pdf"}, content=one)
    assert (same.status_code, same.json()["text_status"]) == (200, "ok")
    bad = client.put(f"/attachments/{first}/file", params={"file_name": "x.pdf"}, content=b"no")
    assert bad.json()["error"]["code"] == "pdf.not_a_pdf"
    gone = client.put(
        "/attachments/nope/file", params={"file_name": "x.pdf"}, content=make_text_pdf([["z"]])
    )
    assert gone.status_code == 404


# --- passages and boxes ----------------------------------------------------------------


def test_locate_ignores_hyphens_breaks_ligatures_and_accents() -> None:
    text = "the inter­\r\ndisciplinary ofﬁce of İstanbul is open"

    place = locate_on_page(text, Quote("interdisciplinary office of istanbul"))

    assert place is not None
    assert text[place.start : place.end] == "inter­\r\ndisciplinary ofﬁce of İstanbul"
    assert locate_on_page(text, Quote("...")) is None


def test_relocate_wants_one_place_it_can_trust() -> None:
    sentence = "a sentence that is long enough to be itself"
    assert relocate(["x", sentence], Quote(sentence), home=0) is not None
    # Twice, and nothing to tell them apart.
    assert relocate([sentence, sentence], Quote(sentence), home=5) is None
    # Twice, told apart by what stands around.
    pages = [f"apple banana cherry {sentence} one", f"delta echo foxtrot {sentence} two"]
    quote = Quote(sentence, prefix="delta echo foxtrot ", suffix=" two")
    place = relocate(pages, quote, home=0)
    assert place is not None and place.index == 1
    # Twice and alike: the one on its old page.
    header = f"journal of studies {sentence} volume one"
    same = Quote(sentence, prefix="journal of studies ", suffix=" volume one")
    place = relocate([header, header, header], same, home=2)
    assert place is not None and place.index == 2


def test_key_maps_back_to_the_text() -> None:
    key = key_of("Dr. ﬁne-tuning")

    assert key.text == "drfinetuning"
    assert key.origin[2] == key.origin[3] == 4


@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_boxes_of_a_passage_over_two_lines(tmp_path: Path, angle: int) -> None:
    path = tmp_path / "x.pdf"
    path.write_bytes(make_text_pdf([["First line here", "Second one there"]], rotate=angle))
    pages = extract_pages(path)
    assert pages is not None
    place = locate_on_page(pages[0].text, Quote("line here second one"))
    assert place is not None

    rects = passage_rects(path, 0, place.start, place.end)

    assert len(rects) == 2
    first, second = rects
    assert first[0] == pytest.approx(72 + 6 * 6.6, abs=2)  # after "First "
    assert second[0] == pytest.approx(72, abs=2)
    assert second[3] < first[3]


def test_merge_lines_joins_a_vertical_line() -> None:
    letters = [(10.0, 100.0 + 8 * i, 20.0, 107.0 + 8 * i) for i in range(5)]

    assert merge_lines(letters) == [(10.0, 100.0, 20.0, 139.0)]
