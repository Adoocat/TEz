"""Deduplication: the plan's table of hard cases, plus identifier normalization."""

from dataclasses import dataclass, field

import pytest

from tez.modules.library.models import IdentifierScheme as Scheme
from tez.modules.library.models import VenueType
from tez.modules.search.dedup import Candidate, PaperIndex, candidate_from, normalized_identifiers
from tez.modules.search.models import MatchMethod
from tez.modules.search.schemas import NormalizedRecord, RecordAuthor
from tez.shared.identifiers import normalize_arxiv, normalize_doi, normalize_isbn

# --- identifiers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("10.1145/3597503.3639187", "10.1145/3597503.3639187"),
        ("10.1145/ABC.Def", "10.1145/abc.def"),
        ("https://doi.org/10.1145/abc", "10.1145/abc"),
        ("http://dx.doi.org/10.1145/abc", "10.1145/abc"),
        ("HTTPS://DOI.ORG/10.1145/ABC", "10.1145/abc"),
        ("doi:10.1145/abc", "10.1145/abc"),
        ("DOI: 10.1145/abc", "10.1145/abc"),
        (" 10.1145/abc. ", "10.1145/abc"),
        ("10.1145/abc,", "10.1145/abc"),
        ("not a doi", None),
        ("", None),
        ("11.1145/abc", None),
        ("10.1145", None),
    ],
)
def test_normalize_doi(given: str, expected: str | None) -> None:
    assert normalize_doi(given) == expected


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("2401.00001", "2401.00001"),
        ("2401.00001v3", "2401.00001"),
        ("arXiv:2401.00001v3", "2401.00001"),
        ("ARXIV:2401.00001", "2401.00001"),
        ("https://arxiv.org/abs/2401.00001v2", "2401.00001"),
        ("http://arxiv.org/pdf/2401.00001v2.pdf", "2401.00001"),
        ("1803.05689v1", "1803.05689"),
        ("0704.0001", "0704.0001"),
        ("cs/0112017v1", "cs/0112017"),
        ("hep-th/9901001", "hep-th/9901001"),
        ("math.GT/0309136", "math.gt/0309136"),
        ("10.48550/arXiv.2507.19902", "2507.19902"),
        ("nonsense", None),
        ("", None),
    ],
)
def test_normalize_arxiv(given: str, expected: str | None) -> None:
    assert normalize_arxiv(given) == expected


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("978-3-16-148410-0", "9783161484100"),
        ("0 306 40615 2", "0306406152"),
        ("080442957x", "080442957X"),
        ("123", None),
    ],
)
def test_normalize_isbn(given: str, expected: str | None) -> None:
    assert normalize_isbn(given) == expected


def test_normalized_identifiers_clean_up_and_drop_what_is_unusable() -> None:
    record = NormalizedRecord(
        title="x",
        identifiers={
            Scheme.DOI: "https://doi.org/10.1000/ABC",
            Scheme.ARXIV: "garbage",
            Scheme.S2: " abc ",
        },
    )

    assert normalized_identifiers(record) == {Scheme.DOI: "10.1000/abc", Scheme.S2: "abc"}


def test_an_arxiv_doi_also_gives_the_arxiv_id() -> None:
    record = NormalizedRecord(title="x", identifiers={Scheme.DOI: "10.48550/arXiv.2507.19902"})

    assert normalized_identifiers(record) == {
        Scheme.DOI: "10.48550/arxiv.2507.19902",
        Scheme.ARXIV: "2507.19902",
    }


# --- the hard cases --------------------------------------------------------------------


TITLE = "Automated Code Review with Large Language Models: An Empirical Study"


@dataclass(frozen=True)
class P:
    """A compact way to write one paper in the table."""

    title: str = TITLE
    year: int | None = 2024
    author: str | None = "Ayşe Yılmaz"
    ids: dict[Scheme, str] = field(default_factory=dict[Scheme, str])
    venue: VenueType | None = VenueType.CONFERENCE

    def record(self) -> NormalizedRecord:
        authors = (RecordAuthor(display_name=self.author),) if self.author else ()
        return NormalizedRecord(
            title=self.title,
            year=self.year,
            authors=authors,
            identifiers=self.ids,
            venue_type=self.venue,
        )


PREPRINT = VenueType.PREPRINT


@pytest.mark.parametrize(
    ("known", "incoming", "method"),
    [
        pytest.param(
            P(ids={Scheme.DOI: "10.1145/abc"}),
            P(title="Something else", ids={Scheme.DOI: "https://doi.org/10.1145/ABC"}),
            MatchMethod.DOI,
            id="doi_case_and_prefix",
        ),
        pytest.param(
            P(ids={Scheme.ARXIV: "2401.00001v1"}, venue=PREPRINT),
            P(title="Renamed in v3", ids={Scheme.ARXIV: "arXiv:2401.00001v3"}, venue=PREPRINT),
            MatchMethod.ID,
            id="arxiv_version_suffix",
        ),
        pytest.param(
            P(ids={Scheme.ARXIV: "2507.19902"}, venue=PREPRINT),
            P(ids={Scheme.DOI: "10.48550/arXiv.2507.19902"}, venue=PREPRINT),
            MatchMethod.ID,
            id="arxiv_id_and_arxiv_doi",
        ),
        pytest.param(
            P(ids={Scheme.S2: "abc"}),
            P(title="Other", year=1999, ids={Scheme.S2: "abc"}),
            MatchMethod.ID,
            id="source_id",
        ),
        pytest.param(
            P(),
            P(title="Automated code-review with large language models - an empirical study."),
            MatchMethod.TITLE_FUZZY,
            id="punctuation_and_case",
        ),
        pytest.param(
            P(title="Yazılım Mühendisliğinde Kod İncelemesi ve Büyük Dil Modelleri"),
            P(
                title="YAZILIM MUHENDISLIGINDE KOD INCELEMESI VE BUYUK DIL MODELLERI",
                author="Ayse Yilmaz",
            ),
            MatchMethod.TITLE_FUZZY,
            id="turkish_letters",
        ),
        pytest.param(
            P(title="Işık ve Gölge: İnceleme Süreçlerinde Yapay Zekâ Kullanımı"),
            P(title="ışık ve gölge: inceleme süreçlerinde yapay zeka kullanımı"),
            MatchMethod.TITLE_FUZZY,
            id="turkish_dotless_i_and_circumflex",
        ),
        pytest.param(
            P(),
            P(title="Automated Code Review with Large Language Modls: An Empirical Study"),
            MatchMethod.TITLE_FUZZY,
            id="small_typo",
        ),
        pytest.param(P(), P(year=2025), MatchMethod.TITLE_FUZZY, id="year_plus_one"),
        pytest.param(P(), P(year=2023), MatchMethod.TITLE_FUZZY, id="year_minus_one"),
        pytest.param(P(), P(author="Y. Yilmaz"), MatchMethod.TITLE_FUZZY, id="initials"),
        pytest.param(P(), P(author="Yılmaz, Ayşe"), MatchMethod.TITLE_FUZZY, id="family_first"),
        pytest.param(P(), P(author=None), MatchMethod.TITLE_FUZZY, id="author_missing_same_title"),
        pytest.param(P(), P(year=None), MatchMethod.TITLE_FUZZY, id="year_missing_same_title"),
        # Must stay separate.
        pytest.param(P(), P(year=2022), MatchMethod.NEW, id="year_too_far"),
        pytest.param(P(), P(author="Mehmet Demir"), MatchMethod.NEW, id="another_author"),
        pytest.param(
            P(ids={Scheme.DOI: "10.1000/a"}),
            P(ids={Scheme.DOI: "10.1000/b"}),
            MatchMethod.NEW,
            id="same_title_different_doi",
        ),
        pytest.param(
            P(ids={Scheme.ARXIV: "2401.00001"}, venue=PREPRINT),
            P(ids={Scheme.ARXIV: "2401.00002"}, venue=PREPRINT),
            MatchMethod.NEW,
            id="same_title_different_arxiv_id",
        ),
        pytest.param(
            P(title="Code Review with LLMs: A Survey of Techniques"),
            P(title="Code Review with LLMs: An Experiment on Teams"),
            MatchMethod.NEW,
            id="similar_titles_different_papers",
        ),
        pytest.param(
            P(title="Modern Code Review at Scale, Part 1"),
            P(title="Modern Code Review at Scale, Part 2"),
            MatchMethod.NEW,
            id="numbered_parts",
        ),
        pytest.param(
            P(title="Modern Code Review at Scale, Part I"),
            P(title="Modern Code Review at Scale, Part II"),
            MatchMethod.NEW,
            id="roman_numbered_parts",
        ),
        pytest.param(P(title="Introduction"), P(title="Introduction"), MatchMethod.NEW, id="short"),
        pytest.param(P(title="???"), P(title="!!!"), MatchMethod.NEW, id="no_letters"),
        pytest.param(
            P(),
            P(title="Automated Code Reviw with Large Language Modls: An Emprical Study", year=None),
            MatchMethod.NEW,
            id="year_missing_needs_near_exact_title",
        ),
    ],
)
def test_hard_cases(known: P, incoming: P, method: MatchMethod) -> None:
    index = PaperIndex([candidate_from("known", known.record())])

    match = index.match(incoming.record())

    assert match.method is method
    if method is MatchMethod.NEW:
        assert match.paper_id is None
    else:
        assert match.paper_id == "known"
        assert match.score is not None and 0 < match.score <= 1


# --- preprint and published version: separate papers, linked (plan, "Sürüm ilişkisi") --


@pytest.mark.parametrize(
    ("known", "incoming"),
    [
        pytest.param(
            P(ids={Scheme.ARXIV: "2401.00001"}, venue=PREPRINT),
            P(ids={Scheme.DOI: "10.1145/abc"}),
            id="preprint_first",
        ),
        pytest.param(
            P(ids={Scheme.DOI: "10.1145/abc"}),
            P(ids={Scheme.ARXIV: "2401.00001"}, venue=PREPRINT),
            id="published_first",
        ),
        pytest.param(
            P(year=2023, ids={Scheme.ARXIV: "2401.00001"}, venue=None),
            P(year=2024, ids={Scheme.DOI: "10.1145/abc"}),
            id="preprint_known_only_by_its_arxiv_id",
        ),
        pytest.param(
            P(ids={Scheme.DOI: "10.48550/arXiv.2401.00001"}, venue=PREPRINT),
            P(ids={Scheme.DOI: "10.1145/abc"}),
            id="different_dois_but_one_is_the_preprint",
        ),
    ],
)
def test_a_preprint_and_its_publication_stay_separate_and_are_linked(known: P, incoming: P) -> None:
    index = PaperIndex([candidate_from("known", known.record())])

    match = index.match(incoming.record())

    assert match.method is MatchMethod.NEW
    assert match.paper_id is None
    assert match.version_of == "known"


def test_two_published_papers_are_not_called_versions() -> None:
    index = PaperIndex([candidate_from("known", P(ids={Scheme.DOI: "10.1000/a"}).record())])

    assert index.match(P(ids={Scheme.DOI: "10.1000/b"}).record()).version_of is None


def test_a_record_with_both_identifiers_matches_by_doi_first() -> None:
    both = P(ids={Scheme.DOI: "10.1000/a", Scheme.ARXIV: "2401.00001"})
    index = PaperIndex(
        [
            candidate_from(
                "preprint", P(ids={Scheme.ARXIV: "2401.00001"}, venue=PREPRINT).record()
            ),
            candidate_from("published", P(ids={Scheme.DOI: "10.1000/a"}).record()),
        ]
    )

    match = index.match(both.record())

    assert match.method is MatchMethod.DOI
    assert match.paper_id == "published"


# --- the index -------------------------------------------------------------------------


def test_papers_added_during_a_search_match_later_records() -> None:
    index = PaperIndex([])
    record = P(ids={Scheme.DOI: "10.1000/a"}).record()

    assert index.match(record).method is MatchMethod.NEW
    index.add(candidate_from("first", record))

    assert index.match(record).paper_id == "first"
    assert index.match(P(title=TITLE + ".").record()).paper_id == "first"


def test_the_best_title_wins_when_several_pass() -> None:
    near = "Automated Code Review with Large Language Modls: An Empirical Study"
    index = PaperIndex(
        [
            candidate_from("near", P(title=near).record()),
            candidate_from("exact", P().record()),
        ]
    )

    assert index.match(P().record()).paper_id == "exact"


def test_candidates_can_be_built_from_stored_columns() -> None:
    index = PaperIndex(
        [
            Candidate(
                paper_id="stored",
                identifiers={Scheme.DOI: "10.1000/a"},
                title_norm="stored paper title about reviews",
                year=2020,
                first_author="yilmaz",
                is_preprint=False,
            )
        ]
    )

    match = index.match(P(title="Stored paper title about reviews", year=2020).record())

    assert match.paper_id == "stored"


def test_matching_a_thousand_records_against_a_thousand_papers_is_quick() -> None:
    papers = [
        P(
            title=f"Study number {i} of topic {i * 7} in software engineering research",
            year=2000 + i % 25,
        )
        for i in range(1000)
    ]
    index = PaperIndex([candidate_from(str(i), p.record()) for i, p in enumerate(papers)])

    matched = sum(index.match(p.record()).paper_id is not None for p in papers)

    assert matched == 1000
