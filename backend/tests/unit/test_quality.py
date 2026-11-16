"""Task 38: quality assessment of the studies included at full text.

Acceptance: a question set with a custom scale and a bundled template, each end to end
through the API; with the stage off, the review panel does not show it (the panel reads
`enabled` from the summary, tested in the web app).
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
from tez.modules.quality.templates import SCALES, TEMPLATES
from tez.modules.reviews.models import Decision, RecordOrigin, ReviewMethod, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService

TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT

# A field's own scale: three levels with Turkish labels and its own scores.
STRENGTH = [
    {"value": "strong", "label": "Güçlü", "score": 2},
    {"value": "moderate", "label": "Orta", "score": 1},
    {"value": "weak", "label": "Zayıf", "score": 0},
    {"value": "na", "label": "Uygulanamaz", "score": None},
]


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
    """A review with four records: two included at full text, one "maybe" at full text,
    one included only at title-abstract."""

    def __init__(self, library: Library) -> None:
        with library.db.write_session() as session:
            papers = LibraryRepository(session)
            ids = [papers.add_paper(f"Çalışma {n}", year=2020 + n).id for n in range(4)]
            reviews = ReviewsRepository(session)
            self.id = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020).id
            for paper_id in ids:
                reviews.add_record(self.id, paper_id, RecordOrigin.DATABASE)
            screening = ScreeningService(session)
            for paper_id in ids:
                screening.decide(self.id, paper_id, TA, Decision.INCLUDE)
            screening.decide(self.id, ids[0], FT, Decision.INCLUDE)
            screening.decide(self.id, ids[1], FT, Decision.INCLUDE)
            screening.decide(self.id, ids[2], FT, Decision.MAYBE)
        self.included = ids[:2]
        self.maybe, self.only_title_abstract = ids[2], ids[3]
        self.base = f"/reviews/{self.id}/quality"


@pytest.fixture
def review(library: Library) -> Review:
    return Review(library)


def ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def error(response: Any, status: int) -> str:
    assert response.status_code == status, response.text
    return response.json()["error"]["code"]


def answer(
    client: TestClient,
    review: Review,
    paper: str,
    question: str,
    value: str | None,
    note: str | None = None,
) -> Any:
    return client.put(
        f"{review.base}/papers/{paper}/answers/{question}", json={"answer": value, "note": note}
    )


# --- acceptance ----------------------------------------------------------------------------


def test_a_custom_scale_question_set_end_to_end(client: TestClient, review: Review) -> None:
    assert ok(client.get(review.base))["enabled"] is False
    assert ok(client.put(f"{review.base}/setting", json={"enabled": True}))["enabled"] is True

    created = ok(
        client.post(
            f"{review.base}/questions",
            json={
                "questions": [
                    {"text": "Araştırma sorusu açık mı?", "scale": {"options": STRENGTH}},
                    {
                        "text": "Örneklem yeterli mi?",
                        "guidance": "Güç analizi raporlandı mı?",
                        "scale": {"options": STRENGTH},
                    },
                ]
            },
        ),
        201,
    )
    q1, q2 = (q["id"] for q in created)
    assert [q["sort_order"] for q in created] == [0, 1]
    assert created[0]["scale"][0] == {"value": "strong", "label": "Güçlü", "score": 2.0}
    assert created[1]["guidance"] == "Güç analizi raporlandı mı?"
    assert created[0]["template"] is None

    # Only papers included at full text are assessed, in screening order.
    rows = ok(client.get(f"{review.base}/papers"))
    assert [r["paper_id"] for r in rows] == review.included
    assert rows[0] == {
        "paper_id": review.included[0],
        "title": "Çalışma 0",
        "year": 2020,
        "first_author": None,
        "answered": 0,
        "questions": 2,
        "score": 0.0,
        "max_score": 4.0,
    }

    first, second = review.included
    ok(answer(client, review, first, q1, "strong"))
    assessed = ok(answer(client, review, first, q2, "moderate", "n = 40, güç analizi yok"))
    assert {a["question_id"]: (a["answer"], a["note"]) for a in assessed["answers"]} == {
        q1: ("strong", None),
        q2: ("moderate", "n = 40, güç analizi yok"),
    }
    # "Not applicable" has no score, so the question leaves the maximum.
    ok(answer(client, review, second, q1, "weak"))
    ok(answer(client, review, second, q2, "na"))

    rows = {r["paper_id"]: r for r in ok(client.get(f"{review.base}/papers"))}
    assert (rows[first]["answered"], rows[first]["score"], rows[first]["max_score"]) == (2, 3, 4)
    assert (rows[second]["answered"], rows[second]["score"], rows[second]["max_score"]) == (2, 0, 2)

    for paper in (review.maybe, review.only_title_abstract):
        assert error(answer(client, review, paper, q1, "strong"), 409) == (
            "quality.paper_not_included"
        )
    assert ok(client.get(f"{review.base}/summary")) == {
        "enabled": True,
        "questions": 2,
        "papers": 2,
        "assessed": 2,
        "in_progress": 0,
    }


def test_a_template_end_to_end(client: TestClient, review: Review) -> None:
    ok(client.put(f"{review.base}/setting", json={"enabled": True}))

    applied = ok(
        client.post(f"{review.base}/templates/nhlbi_case_series", json={"language": "tr"}), 201
    )

    template = TEMPLATES["nhlbi_case_series"]
    assert [q["text"] for q in applied] == [*template.questions, template.rating_question]
    assert {q["template"] for q in applied} == {"nhlbi_case_series"}
    assert [o["label"] for o in applied[0]["scale"]] == [
        "Evet",
        "Hayır",
        "Belirlenemiyor",
        "Raporlanmamış",
        "Uygulanamaz",
    ]
    rating = applied[-1]
    assert [o["value"] for o in rating["scale"]] == ["good", "fair", "poor"]

    paper = review.included[0]
    items = applied[:-1]
    for number, question in enumerate(items):
        ok(answer(client, review, paper, question["id"], "yes" if number < 6 else "no"))
    ok(answer(client, review, paper, rating["id"], "fair", "Takip süresi kısa"))

    row = next(r for r in ok(client.get(f"{review.base}/papers")) if r["paper_id"] == paper)
    # Six "Yes" out of nine items; the overall rating has no score and is not counted.
    assert (row["answered"], row["questions"], row["score"], row["max_score"]) == (10, 10, 6, 9)
    summary = ok(client.get(f"{review.base}/summary"))
    assert (summary["assessed"], summary["in_progress"], summary["papers"]) == (1, 0, 2)


def test_the_stage_is_off_until_turned_on_and_off_keeps_the_work(
    client: TestClient, review: Review
) -> None:
    assert ok(client.get(f"{review.base}/summary"))["enabled"] is False

    ok(client.put(f"{review.base}/setting", json={"enabled": True}))
    question = ok(
        client.post(
            f"{review.base}/questions",
            json={"questions": [{"text": "Q", "scale": {"options": STRENGTH}}]},
        ),
        201,
    )[0]
    ok(answer(client, review, review.included[0], question["id"], "strong"))
    off = ok(client.put(f"{review.base}/setting", json={"enabled": False}))

    assert off["enabled"] is False
    assert [q["id"] for q in off["questions"]] == [question["id"]]
    summary = ok(client.get(f"{review.base}/summary"))
    assert (summary["enabled"], summary["in_progress"], summary["assessed"]) == (False, 0, 1)


# --- catalog and templates -----------------------------------------------------------------


def test_the_catalog_lists_only_redistributable_templates(client: TestClient) -> None:
    catalog = ok(client.get("/quality/catalog"))

    keys = {t["key"] for t in catalog["templates"]}
    assert keys == {
        "nhlbi_controlled_intervention",
        "nhlbi_systematic_review",
        "nhlbi_cohort_cross_sectional",
        "nhlbi_case_control",
        "nhlbi_before_after",
        "nhlbi_case_series",
    }
    for template in catalog["templates"]:
        assert template["license"].startswith("Public domain")
        assert template["source_url"].startswith("https://www.nhlbi.nih.gov/")
        assert template["questions"] and all(q.strip() for q in template["questions"])
    scales = {s["key"]: s for s in catalog["scales"]}
    assert set(scales) >= {"yes_partly_no", "yes_no_unclear_na", "risk_of_bias", "good_fair_poor"}
    assert scales["yes_partly_no"]["options"][1] == {
        "value": "partly",
        "labels": {"en": "Partly", "tr": "Kısmen"},
        "score": 0.5,
    }


def test_every_bundled_scale_and_template_is_well_formed() -> None:
    for preset in SCALES.values():
        values = [o.value for o in preset.options]
        assert len(values) == len(set(values)) >= 2
        assert all(set(o.labels) == {"en", "tr"} for o in preset.options)
    for template in TEMPLATES.values():
        assert template.scale in SCALES
        assert template.rating_scale is None or template.rating_scale in SCALES
        assert len(set(template.questions)) == len(template.questions)


def test_a_template_goes_after_the_reviews_own_questions(
    client: TestClient, review: Review
) -> None:
    own = ok(
        client.post(
            f"{review.base}/questions",
            json={"questions": [{"text": "Kendi sorum", "scale": {"options": STRENGTH}}]},
        ),
        201,
    )
    applied = ok(
        client.post(f"{review.base}/templates/nhlbi_systematic_review", json={"language": "en"}),
        201,
    )

    assert applied[0]["sort_order"] == own[0]["sort_order"] + 1
    assert applied[0]["scale"][0]["label"] == "Yes"
    questions = ok(client.get(review.base))["questions"]
    assert questions[0]["text"] == "Kendi sorum"
    assert len(questions) == 1 + 8 + 1


def test_unknown_template_and_review_are_not_found(client: TestClient, review: Review) -> None:
    unknown = client.post(f"{review.base}/templates/kitchenham", json={"language": "en"})
    assert error(unknown, 404) == "quality.template_unknown"
    assert error(client.get("/reviews/nope/quality"), 404) == "review.not_found"
    assert error(client.get("/reviews/nope/quality/papers"), 404) == "review.not_found"


# --- editing the question set --------------------------------------------------------------


def add(client: TestClient, review: Review, *texts: str) -> list[str]:
    body = {"questions": [{"text": t, "scale": {"options": STRENGTH}} for t in texts]}
    return [q["id"] for q in ok(client.post(f"{review.base}/questions", json=body), 201)]


@pytest.mark.parametrize(
    "scale",
    [
        [{"value": "only", "label": "Only one"}],
        [{"value": "a", "label": "A"}, {"value": "a", "label": "Again"}],
        [{"value": "Bad Value", "label": "A"}, {"value": "b", "label": "B"}],
        [{"value": "a", "label": " "}, {"value": "b", "label": "B"}],
    ],
)
def test_an_invalid_scale_is_rejected(
    client: TestClient, review: Review, scale: list[dict[str, Any]]
) -> None:
    body = {"questions": [{"text": "Q", "scale": {"options": scale}}]}
    assert error(client.post(f"{review.base}/questions", json=body), 422) == "request.invalid"


def test_a_scale_change_keeps_every_used_value(client: TestClient, review: Review) -> None:
    (question,) = add(client, review, "Q")
    ok(answer(client, review, review.included[0], question, "moderate"))
    url = f"{review.base}/questions/{question}"

    relabelled = [{**o, "label": o["label"].upper()} for o in STRENGTH]
    assert ok(client.patch(url, json={"scale": {"options": relabelled}}))["scale"][1] == {
        "value": "moderate",
        "label": "ORTA",
        "score": 1.0,
    }
    without_moderate = [o for o in STRENGTH if o["value"] != "moderate"]
    refused = client.patch(url, json={"scale": {"options": without_moderate}})
    assert error(refused, 409) == "quality.scale_value_in_use"
    assert refused.json()["error"]["params"] == {"values": ["moderate"]}


def test_editing_text_and_clearing_guidance(client: TestClient, review: Review) -> None:
    (question,) = add(client, review, "Eski")
    url = f"{review.base}/questions/{question}"
    ok(client.patch(url, json={"guidance": "İpucu"}))

    edited = ok(client.patch(url, json={"text": " Yeni ", "guidance": None}))

    assert (edited["text"], edited["guidance"]) == ("Yeni", None)


def test_an_answered_question_cannot_be_deleted(client: TestClient, review: Review) -> None:
    used, unused = add(client, review, "Used", "Unused")
    ok(answer(client, review, review.included[0], used, "weak"))

    assert error(client.delete(f"{review.base}/questions/{used}"), 409) == (
        "quality.question_in_use"
    )
    assert client.delete(f"{review.base}/questions/{unused}").status_code == 204
    assert [q["id"] for q in ok(client.get(review.base))["questions"]] == [used]
    assert error(client.delete(f"{review.base}/questions/{unused}"), 404) == (
        "quality.question_not_found"
    )


def test_questions_can_be_reordered(client: TestClient, review: Review) -> None:
    a, b, c = add(client, review, "A", "B", "C")

    ok(client.put(f"{review.base}/order", json={"question_ids": [c, a, b]}))

    assert [q["text"] for q in ok(client.get(review.base))["questions"]] == ["C", "A", "B"]
    partial = client.put(f"{review.base}/order", json={"question_ids": [c, a]})
    assert error(partial, 400) == "quality.order_mismatch"
    repeated = client.put(f"{review.base}/order", json={"question_ids": [c, a, a]})
    assert error(repeated, 400) == "quality.order_mismatch"


def test_a_question_of_another_review_is_not_found(
    client: TestClient, review: Review, library: Library
) -> None:
    other = Review(library)
    (foreign,) = add(client, other, "Theirs")

    assert error(client.patch(f"{review.base}/questions/{foreign}", json={"text": "x"}), 404) == (
        "quality.question_not_found"
    )
    assert error(answer(client, review, review.included[0], foreign, "strong"), 404) == (
        "quality.question_not_found"
    )


# --- answers -------------------------------------------------------------------------------


def test_an_answer_outside_the_scale_is_refused(client: TestClient, review: Review) -> None:
    (question,) = add(client, review, "Q")

    refused = answer(client, review, review.included[0], question, "excellent")

    assert error(refused, 400) == "quality.answer_invalid"


def test_answers_change_and_clear(client: TestClient, review: Review) -> None:
    (question,) = add(client, review, "Q")
    paper = review.included[0]

    ok(answer(client, review, paper, question, "weak"))
    changed = ok(answer(client, review, paper, question, "strong", "Gözden geçirildi"))
    assert [(a["answer"], a["note"]) for a in changed["answers"]] == [
        ("strong", "Gözden geçirildi")
    ]
    note_only = ok(answer(client, review, paper, question, None, "Yazara sorulacak"))
    assert [(a["answer"], a["note"]) for a in note_only["answers"]] == [(None, "Yazara sorulacak")]
    row = ok(client.get(f"{review.base}/papers"))[0]
    assert row["answered"] == 0

    cleared = ok(answer(client, review, paper, question, None, " "))
    assert cleared["answers"] == []
    # Clearing the only answer frees the question again.
    assert client.delete(f"{review.base}/questions/{question}").status_code == 204


def test_a_paper_that_leaves_full_text_inclusion_leaves_the_list(
    client: TestClient, review: Review, library: Library
) -> None:
    (question,) = add(client, review, "Q")
    paper = review.included[1]
    ok(answer(client, review, paper, question, "strong"))

    with library.db.write_session() as session:
        ScreeningService(session).decide(review.id, paper, FT, Decision.MAYBE)

    assert [r["paper_id"] for r in ok(client.get(f"{review.base}/papers"))] == [review.included[0]]
    assert error(client.get(f"{review.base}/papers/{paper}"), 409) == "quality.paper_not_included"
