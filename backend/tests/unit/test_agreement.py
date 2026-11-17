"""Task 42: agreement between two reviewers, Cohen's kappa per stage, conflicts and their
reconciliation. Kappa is checked against examples worked out by hand."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.dual_screening.agreement import cohen_kappa, outcome, stage_agreement
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput
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
from tez.modules.settings.secrets import MemorySecretStore

TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT
INC, EXC, MAY = Decision.INCLUDE, Decision.EXCLUDE, Decision.MAYBE


# --- Cohen's kappa, against hand-worked examples ------------------------------------------


def test_kappa_of_a_two_by_two_table() -> None:
    # 50 records: both yes 20, both no 15, A yes / B no 5, A no / B yes 10.
    # po = 35/50 = 0.70; A says yes 25/50, B 30/50; pe = 0.5*0.6 + 0.5*0.4 = 0.50;
    # kappa = (0.70 - 0.50) / (1 - 0.50) = 0.40.
    pairs = [("y", "y")] * 20 + [("n", "n")] * 15 + [("y", "n")] * 5 + [("n", "y")] * 10

    assert cohen_kappa(pairs) == pytest.approx(0.40)


def test_kappa_of_three_categories() -> None:
    # Rows: A's choice; columns: B's (include, exclude, maybe).
    #            inc exc may
    #     inc     10   2   3   (15)
    #     exc      1  15   2   (18)
    #     may      2   1   4   ( 7)
    #             (13) (18) (9)   n = 40
    # po = 29/40 = 0.725; pe = (15*13 + 18*18 + 7*9) / 1600 = 582/1600 = 0.36375;
    # kappa = 0.36125 / 0.63625 = 0.567780...
    table = {
        ("i", "i"): 10,
        ("i", "e"): 2,
        ("i", "m"): 3,
        ("e", "i"): 1,
        ("e", "e"): 15,
        ("e", "m"): 2,
        ("m", "i"): 2,
        ("m", "e"): 1,
        ("m", "m"): 4,
    }
    pairs = [pair for pair, count in table.items() for _ in range(count)]

    assert cohen_kappa(pairs) == pytest.approx(0.36125 / 0.63625)
    assert cohen_kappa(pairs) == pytest.approx(0.567780, abs=1e-6)


def test_kappa_edges() -> None:
    assert cohen_kappa([("y", "y"), ("n", "n")]) == pytest.approx(1.0)
    # Agreement no better than chance: po = 0.5, pe = 0.5.
    assert cohen_kappa([("y", "y"), ("y", "n"), ("n", "y"), ("n", "n")]) == pytest.approx(0.0)
    # Undefined: nothing to compare, or one category throughout (pe = 1).
    assert cohen_kappa([]) is None
    assert cohen_kappa([("y", "y")] * 5) is None


def test_at_title_abstract_include_and_maybe_agree() -> None:
    assert outcome(TA, INC) == outcome(TA, MAY) != outcome(TA, EXC)
    assert outcome(FT, INC) != outcome(FT, MAY)

    result = stage_agreement(
        TA, {"a": INC, "b": EXC, "c": MAY}, {"a": MAY, "b": EXC, "c": EXC, "d": INC}
    )

    # "d" was decided by one reviewer only, so it is not compared.
    assert (result.compared, result.agreed) == (3, 2)
    assert result.percent == pytest.approx(200 / 3)


# --- Through the API: agreement, conflicts, reconciliation, PRISMA --------------------------


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    library = open_library(tmp_path / "lib", create=True)
    yield library
    library.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def _seed(library: Library) -> tuple[str, list[str], str]:
    """Ten records. Title-abstract, owner vs Ayşe (I/M advance, E excludes):

    record:  0  1  2  3  4  5  6  7  8  9
    owner:   I  I  I  M  I  E  E  E  E  I
    Ayşe:    I  M  E  I  E  E  E  I  E  I

    Outcomes agree on 0,1,3,5,6,8,9 (7 of 10); conflicts on 2,4,7.
    Advance/exclude: owner 6/4, Ayşe 5/5; po = 0.7; pe = 0.6*0.5 + 0.4*0.5 = 0.5;
    kappa = 0.2 / 0.5 = 0.4.
    """
    owner = [INC, INC, INC, MAY, INC, EXC, EXC, EXC, EXC, INC]
    ayse = [INC, MAY, EXC, INC, EXC, EXC, EXC, INC, EXC, INC]
    with library.db.write_session() as session:
        papers = PaperService(session)
        ids = [
            papers.add(
                f"Study number {n} on teacher burnout",
                identifiers={},
                authors=[AuthorInput(f"Author {n}", family=f"Author{n}")],
                year=2020,
            ).id
            for n in range(10)
        ]
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020)
        for paper_id in ids:
            reviews.add_record(review.id, paper_id, RecordOrigin.DATABASE)
        reason = reviews.add_criterion(review.id, CriterionKind.EXCLUSION, "E1", "Not empirical")
        screening = ScreeningService(session)
        for paper_id, mine, hers in zip(ids, owner, ayse, strict=True):
            for who, decision in (("owner", mine), ("Ayşe", hers)):
                screening.decide(
                    review.id,
                    paper_id,
                    TA,
                    decision,
                    criterion_id=reason.id if decision is EXC else None,
                    reviewer=who,
                )
        return review.id, ids, reason.id


def test_agreement_and_kappa_per_stage(client: TestClient, library: Library) -> None:
    review_id, _, _ = _seed(library)

    body = client.get(f"/reviews/{review_id}/decisions/agreement").json()

    assert (body["reviewer"], body["reviewers"]) == ("Ayşe", ["Ayşe"])
    ta, ft = body["stages"]
    assert (ta["stage"], ta["compared"], ta["agreed"], ta["conflicts"]) == (
        "title_abstract",
        10,
        7,
        3,
    )
    assert ta["percent"] == pytest.approx(70.0)
    assert ta["kappa"] == pytest.approx(0.4)
    assert (ft["compared"], ft["kappa"], ft["percent"]) == (0, None, None)


def test_reconciling_empties_the_conflict_list(client: TestClient, library: Library) -> None:
    review_id, ids, reason = _seed(library)
    url = f"/reviews/{review_id}/decisions/conflicts/title_abstract"

    listed = client.get(url).json()
    assert [item["paper_id"] for item in listed["items"]] == [ids[2], ids[4], ids[7]]
    first = listed["items"][0]
    assert (first["owner"]["decision"], first["other"]["decision"]) == ("include", "exclude")
    assert (first["other"]["criterion_code"], first["other"]["criterion_text"]) == (
        "E1",
        "Not empirical",
    )

    for paper_id, decision in ((ids[2], "exclude"), (ids[4], "include"), (ids[7], "exclude")):
        made = client.post(
            f"{url}/reconcile",
            json={
                "paper_id": paper_id,
                "decision": decision,
                "criterion_id": reason if decision == "exclude" else None,
            },
        ).json()
        assert made["reviewer"] == "consensus"

    assert client.get(url).json()["items"] == []
    stages = client.get(f"/reviews/{review_id}/decisions/agreement").json()["stages"]
    # Kappa compares the reviewers' own decisions, so reconciling leaves it as it was.
    assert (stages[0]["conflicts"], stages[0]["kappa"]) == (0, pytest.approx(0.4))


def test_prisma_counts_reconciled_decisions(client: TestClient, library: Library) -> None:
    review_id, ids, reason = _seed(library)
    prisma = f"/reviews/{review_id}/prisma"
    before = client.get(prisma).json()["databases"]
    # The owner alone: 6 advance to full text, 4 excluded.
    assert (before["excluded"], before["sought"]) == (4, 6)

    # Record 2: owner include, Ayşe exclude; reconciled as exclude.
    client.post(
        f"/reviews/{review_id}/decisions/conflicts/title_abstract/reconcile",
        json={"paper_id": ids[2], "decision": "exclude", "criterion_id": reason},
    )
    # Record 7: owner exclude, Ayşe include; reconciled as include, then included at full text.
    client.post(
        f"/reviews/{review_id}/decisions/conflicts/title_abstract/reconcile",
        json={"paper_id": ids[7], "decision": "include"},
    )
    full_text = client.post(
        f"/reviews/{review_id}/decisions/conflicts/full_text/reconcile",
        json={"paper_id": ids[7], "decision": "include"},
    )
    after = client.get(prisma).json()

    assert full_text.status_code == 200
    assert (after["databases"]["excluded"], after["databases"]["sought"]) == (4, 6)
    assert after["included"] == 1
    # The owner's screening queue is still the owner's own: record 7 is excluded there.
    queue = client.get(
        f"/reviews/{review_id}/screening/title_abstract", params={"filter": "exclude"}
    ).json()
    assert ids[7] in [item["paper_id"] for item in queue["items"]]


def test_reconciling_needs_the_reconciled_title_abstract_outcome(
    client: TestClient, library: Library
) -> None:
    review_id, ids, _ = _seed(library)

    # Record 5: both excluded it, nothing reconciled, so it never reached full text.
    refused = client.post(
        f"/reviews/{review_id}/decisions/conflicts/full_text/reconcile",
        json={"paper_id": ids[5], "decision": "include"},
    )

    assert refused.json()["error"]["code"] == "screening.stage_not_reached"


def test_an_unknown_colleague_and_no_colleague(client: TestClient, library: Library) -> None:
    review_id, _, _ = _seed(library)
    unknown = client.get(f"/reviews/{review_id}/decisions/agreement", params={"reviewer": "Nobody"})
    with library.db.write_session() as session:
        alone = ReviewsRepository(session).add_review("Alone", method=ReviewMethod.PRISMA2020).id
    empty = client.get(f"/reviews/{alone}/decisions/conflicts/title_abstract").json()

    assert unknown.json()["error"]["code"] == "request.invalid"
    assert (empty["reviewer"], empty["items"]) == (None, [])
