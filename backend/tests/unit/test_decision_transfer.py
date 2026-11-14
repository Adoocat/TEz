"""Task 41: one reviewer's decisions travel to a colleague's library as a versioned JSON file."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tez.core.errors import ErrorCode, TezError
from tez.modules.dual_screening.building import (
    CriterionInfo,
    DecisionInfo,
    ReviewInfo,
    build_file,
)
from tez.modules.dual_screening.fileformat import (
    VERSION,
    DecisionFile,
    FileRecord,
    dump_decision_file,
    json_schema,
    parse_decision_file,
)
from tez.modules.dual_screening.matching import MatchProblem, RecordMatch, match_records
from tez.modules.dual_screening.planning import (
    DecisionKey,
    ExistingDecision,
    ImportPlan,
    PlannedDecision,
    plan_import,
)
from tez.modules.library.models import IdentifierScheme as Scheme
from tez.modules.library.models import VenueType
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
from tez.modules.search.models import MatchMethod

SCHEMA_FILE = Path(__file__).parents[3] / "docs" / "formats" / "screening-decisions.v1.schema.json"
WHEN = datetime(2026, 11, 14, 9, 30, tzinfo=UTC)
TA = ScreeningStage.TITLE_ABSTRACT
FT = ScreeningStage.FULL_TEXT


def _paper(
    papers: PaperService,
    title: str,
    author: str,
    year: int,
    identifiers: dict[Scheme, str] | None = None,
    venue_type: VenueType | None = None,
) -> str:
    family = author.split()[-1]
    return papers.add(
        title,
        identifiers=identifiers or {},
        authors=[AuthorInput(author, family=family)],
        year=year,
        venue_type=venue_type,
    ).id


@pytest.fixture
def ayse(tmp_path: Path) -> Iterator[tuple[Library, str, dict[str, str]]]:
    """Ayşe's library: the review she screened, and her papers by a short name."""
    library = open_library(tmp_path / "ayse", create=True)
    with library.db.write_session() as session:
        papers = PaperService(session)
        ids = {
            "doi": _paper(
                papers,
                "Deep Learning for Code Review",
                "Ayşe Yılmaz",
                2021,
                {Scheme.DOI: "10.1000/ABC.1"},
                VenueType.JOURNAL,
            ),
            "arxiv": _paper(
                papers,
                "Transformers in Program Repair",
                "Jo Kim",
                2020,
                {Scheme.ARXIV: "2101.00001v2"},
                VenueType.PREPRINT,
            ),
            "title": _paper(
                papers,
                "Öğretmen Adaylarının Dijital Okuryazarlık Düzeyleri",
                "Elif Şahin",
                2019,
            ),
            "only_ayse": _paper(papers, "A Study Only Ayşe Found", "Can Demir", 2018),
            "outside": _paper(
                papers, "Kept But Not Reviewed", "Lee Park", 2022, {Scheme.DOI: "10.1000/x.9"}
            ),
        }
        reviews = ReviewsRepository(session)
        review = reviews.add_review("Digital literacy", method=ReviewMethod.PRISMA2020)
        for paper_id in ids.values():
            reviews.add_record(review.id, paper_id, RecordOrigin.DATABASE)
        review_id = review.id
    yield library, review_id, ids
    library.close()


@pytest.fixture
def demirkan(tmp_path: Path) -> Iterator[tuple[Library, str, dict[str, str]]]:
    """Demirkan's library: the same review, the same papers under other ids and spellings."""
    library = open_library(tmp_path / "demirkan", create=True)
    with library.db.write_session() as session:
        papers = PaperService(session)
        ids = {
            "doi": _paper(
                papers,
                "Deep learning for code review.",
                "A. Yılmaz",
                2021,
                {Scheme.DOI: "10.1000/abc.1"},
                VenueType.JOURNAL,
            ),
            "arxiv": _paper(
                papers,
                "Transformers in program repair",
                "J. Kim",
                2020,
                {Scheme.ARXIV: "2101.00001"},
                VenueType.PREPRINT,
            ),
            "title": _paper(
                papers,
                "Ogretmen adaylarinin dijital okuryazarlik duzeyleri",
                "E. Sahin",
                2019,
            ),
            "outside": _paper(
                papers, "Kept but not reviewed", "L. Park", 2022, {Scheme.DOI: "10.1000/x.9"}
            ),
        }
        reviews = ReviewsRepository(session)
        review = reviews.add_review("Digital literacy (D)", method=ReviewMethod.PRISMA2020)
        for name in ("doi", "arxiv", "title"):
            reviews.add_record(review.id, ids[name], RecordOrigin.DATABASE)
        reviews.add_criterion(review.id, CriterionKind.EXCLUSION, "E1", "Not empirical")
        reviews.add_criterion(review.id, CriterionKind.INCLUSION, "I1", "Teacher education")
        criteria = {c.code: c.id for c in reviews.criteria(review.id)}
        review_id = review.id
    yield library, review_id, ids | {f"criterion:{k}": v for k, v in criteria.items()}
    library.close()


def _ayse_file(
    ayse: tuple[Library, str, dict[str, str]], decisions: list[DecisionInfo] | None = None
) -> DecisionFile:
    library, review_id, ids = ayse
    if decisions is None:
        decisions = [
            DecisionInfo("d1", ids["doi"], TA, Decision.INCLUDE, "I1", None, WHEN),
            DecisionInfo("d2", ids["doi"], FT, Decision.EXCLUDE, "E1", "No data", WHEN),
            DecisionInfo("d3", ids["arxiv"], TA, Decision.EXCLUDE, "E1", None, WHEN),
            DecisionInfo("d4", ids["title"], TA, Decision.MAYBE, None, "  ", WHEN),
            DecisionInfo("d5", ids["only_ayse"], TA, Decision.INCLUDE, None, None, WHEN),
            DecisionInfo("d6", ids["outside"], TA, Decision.INCLUDE, None, None, WHEN),
        ]
    with library.db.session() as session:
        cards = PaperService(session).cards(ids.values())
    return build_file(
        review=ReviewInfo(review_id, "Digital literacy", ReviewMethod.PRISMA2020),
        reviewer="Ayşe Yılmaz",
        criteria=[
            CriterionInfo("I1", CriterionKind.INCLUSION, "Teacher education", None),
            CriterionInfo("E1", CriterionKind.EXCLUSION, "Not empirical", None),
        ],
        decisions=decisions,
        cards=cards,
        exported_at=WHEN,
    )


# --- The file format -------------------------------------------------------------------------


def test_a_decision_file_reads_back_as_written(ayse: tuple[Library, str, dict[str, str]]) -> None:
    document = _ayse_file(ayse)
    text = dump_decision_file(document)
    raw = json.loads(text)
    assert (raw["format"], raw["version"]) == ("tez.screening-decisions", VERSION)
    assert raw["reviewer"] == "Ayşe Yılmaz"
    record = next(r for r in raw["records"] if r["ref"] == ayse[2]["doi"])
    assert record["identifiers"] == {"doi": "10.1000/ABC.1"}
    assert record["first_author"] == {"display_name": "Ayşe Yılmaz", "family": "Yılmaz"}
    assert parse_decision_file(text) == document
    assert parse_decision_file(text.encode()) == document


def test_only_records_with_decisions_are_written(
    ayse: tuple[Library, str, dict[str, str]],
) -> None:
    ids = ayse[2]
    document = _ayse_file(
        ayse, [DecisionInfo("d1", ids["doi"], TA, Decision.INCLUDE, None, None, WHEN)]
    )
    assert [record.ref for record in document.records] == [ids["doi"]]


def _error(content: str | bytes) -> TezError:
    with pytest.raises(TezError) as caught:
        parse_decision_file(content)
    return caught.value


def _raw(ayse: tuple[Library, str, dict[str, str]]) -> dict[str, object]:
    return json.loads(dump_decision_file(_ayse_file(ayse)))


def test_a_file_that_is_not_a_decision_file_is_rejected() -> None:
    assert _error("not json").code is ErrorCode.DECISIONS_INVALID_FILE
    assert _error(b"\xff\xfe").params == {"reason": "not_json"}
    assert _error('{"format": "bibtex"}').params == {"reason": "not_a_decision_file"}
    assert _error("[]").params == {"reason": "not_a_decision_file"}


def test_a_newer_version_is_named_not_misread(ayse: tuple[Library, str, dict[str, str]]) -> None:
    raw = _raw(ayse) | {"version": 2}
    error = _error(json.dumps(raw))
    assert error.code is ErrorCode.DECISIONS_UNSUPPORTED_VERSION
    assert error.params == {"version": 2, "supported": 1}


@pytest.mark.parametrize("name", ["owner", " Consensus "])
def test_reserved_reviewer_names_are_rejected(
    ayse: tuple[Library, str, dict[str, str]], name: str
) -> None:
    raw = _raw(ayse) | {"reviewer": name}
    assert _error(json.dumps(raw)).code is ErrorCode.DECISIONS_RESERVED_REVIEWER


def test_inconsistent_files_are_rejected(ayse: tuple[Library, str, dict[str, str]]) -> None:
    raw = _raw(ayse)
    decisions = raw["decisions"]
    assert isinstance(decisions, list)
    dangling = raw | {"decisions": [*decisions, {**decisions[0], "id": "x", "record": "nope"}]}
    twice = raw | {"decisions": [*decisions, {**decisions[0], "id": "x"}]}
    unknown_decision = raw | {"decisions": [{**decisions[0], "decision": "perhaps"}]}
    for bad in (dangling, twice, unknown_decision):
        error = _error(json.dumps(bad))
        assert error.code is ErrorCode.DECISIONS_INVALID_FILE
        assert error.params["reason"] == "invalid"


def test_the_published_json_schema_is_current() -> None:
    """docs/formats holds the schema others can validate files with; regenerate it on change."""
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == json_schema()


# --- Matching records across libraries ---------------------------------------------------------


def test_records_are_matched_by_identifier_then_title(
    ayse: tuple[Library, str, dict[str, str]], demirkan: tuple[Library, str, dict[str, str]]
) -> None:
    document = _ayse_file(ayse)
    library, review_id, ids = demirkan
    by_ref = {m.ref: m for m in match_records(library.db, review_id, document.records)}
    theirs = ayse[2]
    assert by_ref[theirs["doi"]] == RecordMatch(theirs["doi"], ids["doi"], MatchMethod.DOI)
    assert by_ref[theirs["arxiv"]] == RecordMatch(theirs["arxiv"], ids["arxiv"], MatchMethod.ID)
    title = by_ref[theirs["title"]]
    assert (title.paper_id, title.method) == (ids["title"], MatchMethod.TITLE_FUZZY)
    assert by_ref[theirs["only_ayse"]].problem is MatchProblem.NOT_FOUND
    assert by_ref[theirs["outside"]].problem is MatchProblem.NOT_IN_REVIEW
    assert by_ref[theirs["outside"]].paper_id is None


def test_a_paper_is_matched_by_one_record_only(
    demirkan: tuple[Library, str, dict[str, str]],
) -> None:
    library, review_id, ids = demirkan
    records = [
        FileRecord(
            ref="a", title="Deep learning for code review", identifiers={"doi": "10.1000/abc.1"}
        ),
        FileRecord(ref="b", title="Another title", identifiers={"doi": "doi:10.1000/ABC.1"}),
        FileRecord(ref="c", title="Unknown", identifiers={"pmid": "123", "doi": "not a doi"}),
    ]
    matches = match_records(library.db, review_id, records)
    assert [(m.paper_id, m.problem) for m in matches] == [
        (ids["doi"], None),
        (None, MatchProblem.DUPLICATE),
        (None, MatchProblem.NOT_FOUND),
    ]


# --- Planning an import: append-only and idempotent ----------------------------------------------


def _plan_into_demirkan(
    document: DecisionFile,
    demirkan: tuple[Library, str, dict[str, str]],
    existing: dict[DecisionKey, ExistingDecision],
) -> ImportPlan:
    library, review_id, ids = demirkan
    matches = match_records(library.db, review_id, document.records)
    criteria = {
        k.removeprefix("criterion:"): v for k, v in ids.items() if k.startswith("criterion:")
    }
    return plan_import(document, matches, criteria, existing)


def _applied(
    plan_writes: list[PlannedDecision], existing: dict[DecisionKey, ExistingDecision]
) -> dict[DecisionKey, ExistingDecision]:
    """What the reviewer's decisions in force become once the planned rows are written."""
    result = dict(existing)
    for number, write in enumerate(plan_writes):
        result[(write.paper_id, write.stage)] = ExistingDecision(
            f"row{len(existing)}-{number}", write.decision, write.criterion_id, write.note
        )
    return result


def test_importing_adds_matched_decisions_and_reports_the_rest(
    ayse: tuple[Library, str, dict[str, str]], demirkan: tuple[Library, str, dict[str, str]]
) -> None:
    ids = demirkan[2]
    plan = _plan_into_demirkan(_ayse_file(ayse), demirkan, {})
    assert [(w.paper_id, w.stage, w.decision, w.source_id) for w in plan.writes] == [
        (ids["doi"], TA, Decision.INCLUDE, "d1"),
        (ids["arxiv"], TA, Decision.EXCLUDE, "d3"),
        (ids["title"], TA, Decision.MAYBE, "d4"),
        (ids["doi"], FT, Decision.EXCLUDE, "d2"),
    ]
    assert plan.writes[1].criterion_id == ids["criterion:E1"]
    assert plan.writes[2].note is None  # A blank note is no note.
    assert plan.writes[3].note == "No data"
    assert (plan.added, plan.corrected, plan.unchanged) == (4, 0, 0)
    assert plan.unmatched_decisions == 2
    assert plan.unknown_criteria == {}


def test_importing_the_same_file_twice_adds_nothing(
    ayse: tuple[Library, str, dict[str, str]], demirkan: tuple[Library, str, dict[str, str]]
) -> None:
    document = _ayse_file(ayse)
    first = _plan_into_demirkan(document, demirkan, {})
    again = _plan_into_demirkan(document, demirkan, _applied(first.writes, {}))
    assert again.writes == []
    assert (again.unchanged, again.withdrawn) == (4, 0)


def test_a_changed_decision_is_a_correction_of_the_imported_row(
    ayse: tuple[Library, str, dict[str, str]], demirkan: tuple[Library, str, dict[str, str]]
) -> None:
    theirs, ids = ayse[2], demirkan[2]
    existing = _applied(_plan_into_demirkan(_ayse_file(ayse), demirkan, {}).writes, {})
    corrected = _ayse_file(
        ayse,
        [
            DecisionInfo("d7", theirs["doi"], TA, Decision.EXCLUDE, "E1", None, WHEN),
            DecisionInfo("d3", theirs["arxiv"], TA, Decision.EXCLUDE, "E1", None, WHEN),
            DecisionInfo("d4", theirs["title"], TA, Decision.MAYBE, None, None, WHEN),
        ],
    )
    plan = _plan_into_demirkan(corrected, demirkan, existing)
    (write,) = plan.writes
    assert (write.paper_id, write.stage, write.decision) == (ids["doi"], TA, Decision.EXCLUDE)
    assert write.supersedes_id == existing[(ids["doi"], TA)].id
    assert (plan.added, plan.corrected, plan.unchanged) == (0, 1, 2)
    # The full-text decision is no longer in the file; it stays, and the report says so.
    assert plan.withdrawn == 1


def test_a_criterion_this_review_lacks_is_reported_not_guessed(
    ayse: tuple[Library, str, dict[str, str]], demirkan: tuple[Library, str, dict[str, str]]
) -> None:
    theirs = ayse[2]
    document = _ayse_file(
        ayse,
        [
            DecisionInfo("d1", theirs["doi"], TA, Decision.EXCLUDE, "E9", None, WHEN),
            DecisionInfo("d3", theirs["arxiv"], TA, Decision.EXCLUDE, "E9", None, WHEN),
        ],
    )
    plan = _plan_into_demirkan(document, demirkan, {})
    assert plan.writes == []
    assert plan.unknown_criteria == {"E9": 2}
