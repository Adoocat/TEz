"""Formatted bibliographies (Task 39): each bundled style, in Turkish and English, for a book,
a chapter, an article, a conference paper and a thesis. The expected text was checked against
the style guides; it also pins the citeproc-py fixes in `csl_compat` (full given names in MLA
and Chicago, no "(Publication)" in APA, "İçinde", punctuation inside quotes in US English, a
space after "[1]")."""
# The expected entries are whole bibliography lines, with the en dashes the styles print.
# ruff: noqa: E501, RUF001

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.export.csl import CslLocale, CslStyle, render
from tez.modules.export.writers import ExportAuthor, ExportPaper
from tez.modules.library.models import IdentifierScheme, ThesisType, VenueType
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput
from tez.modules.library.service import Library, open_library
from tez.modules.reviews.models import Decision, RecordOrigin, ReviewMethod, ScreeningStage
from tez.modules.reviews.repository import ReviewsRepository
from tez.modules.screening.service import ScreeningService
from tez.modules.settings.secrets import MemorySecretStore


def _paper(
    citekey: str,
    title: str,
    authors: list[tuple[str, str]],
    year: int,
    venue: str,
    venue_type: VenueType,
    *,
    thesis_type: ThesisType | None = None,
    volume: str | None = None,
    issue: str | None = None,
    pages: str | None = None,
    doi: str | None = None,
    language: str | None = None,
) -> ExportPaper:
    return ExportPaper(
        citekey=citekey,
        title=title,
        authors=tuple(
            ExportAuthor(f"{given} {family}", family, given) for family, given in authors
        ),
        year=year,
        venue=venue,
        venue_type=venue_type,
        thesis_type=thesis_type,
        volume=volume,
        issue=issue,
        pages=pages,
        doi=doi,
        arxiv=None,
        isbn=None,
        url=None,
        abstract=None,
        language=language,
    )


ARTICLE = _paper(
    "yilmaz2021",
    "Yapay zekâ ile ölçek geliştirme",
    [("Yılmaz", "İsmail"), ("Öztürk", "Ayşe")],
    2021,
    "Türk Psikoloji Dergisi",
    VenueType.JOURNAL,
    volume="36",
    issue="2",
    pages="45\N{EN DASH}67",
    doi="10.1234/tpd.2021.1",
    language="tr",
)
BOOK = _paper(
    "creswell2014",
    "Research design",
    [("Creswell", "John W.")],
    2014,
    "SAGE",
    VenueType.BOOK,
    language="en",
)
CHAPTER = _paper(
    "charmaz2008",
    "Grounded theory",
    [("Charmaz", "Kathy")],
    2008,
    "Handbook of emergent methods",
    VenueType.CHAPTER,
    pages="155-170",
    language="en",
)
CONFERENCE = _paper(
    "vaswani2017",
    "Attention is all you need",
    [("Vaswani", "Ashish")],
    2017,
    "Advances in Neural Information Processing Systems",
    VenueType.CONFERENCE,
    pages="5998-6008",
    language="en",
)
THESIS = _paper(
    "dogru2026",
    "Kod modelleri",
    [("Doğru", "Demirkan")],
    2026,
    "Orta Doğu Teknik Üniversitesi",
    VenueType.THESIS,
    thesis_type=ThesisType.MASTERS,
    language="tr",
)
SAMPLES = [ARTICLE, BOOK, CHAPTER, CONFERENCE, THESIS]

# Numbered styles keep the given order; the others sort by author.
EXPECTED: dict[tuple[CslStyle, CslLocale], dict[str, str]] = {
    (CslStyle.APA, CslLocale.TR): {
        "charmaz2008": "Charmaz, K. (2008). Grounded theory. İçinde Handbook of emergent methods (ss. 155-170).",
        "creswell2014": "Creswell, J. W. (2014). Research design. SAGE.",
        "dogru2026": "Doğru, D. (2026). Kod modelleri [Yüksek lisans tezi]. Orta Doğu Teknik Üniversitesi.",
        "vaswani2017": "Vaswani, A. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 5998-6008.",
        "yilmaz2021": "Yılmaz, İ., & Öztürk, A. (2021). Yapay zekâ ile ölçek geliştirme. Türk Psikoloji Dergisi, 36(2), 45-67. https://doi.org/10.1234/tpd.2021.1",
    },
    (CslStyle.APA, CslLocale.EN): {
        "charmaz2008": "Charmaz, K. (2008). Grounded theory. In Handbook of emergent methods (pp. 155–170).",
        "creswell2014": "Creswell, J. W. (2014). Research design. SAGE.",
        "dogru2026": "Doğru, D. (2026). Kod modelleri [Master's thesis]. Orta Doğu Teknik Üniversitesi.",
        "vaswani2017": "Vaswani, A. (2017). Attention is all you need. Advances in Neural Information Processing Systems, 5998–6008.",
        "yilmaz2021": "Yılmaz, İ., & Öztürk, A. (2021). Yapay zekâ ile ölçek geliştirme. Türk Psikoloji Dergisi, 36(2), 45–67. https://doi.org/10.1234/tpd.2021.1",
    },
    (CslStyle.MLA, CslLocale.TR): {
        "charmaz2008": "Charmaz, Kathy. “Grounded Theory”. Handbook of Emergent Methods, 2008, ss. 155-70.",
        "creswell2014": "Creswell, John W. Research Design. SAGE, 2014.",
        "dogru2026": "Doğru, Demirkan. Kod modelleri. 2026. Orta Doğu Teknik Üniversitesi, Yüksek lisans tezi.",
        "vaswani2017": "Vaswani, Ashish. “Attention Is All You Need”. Advances in Neural Information Processing Systems, 2017, ss. 5998-6008.",
        "yilmaz2021": "Yılmaz, İsmail, ve Ayşe Öztürk. “Yapay zekâ ile ölçek geliştirme”. Türk Psikoloji Dergisi, c. 36, sy. 2, 2021, ss. 45-67, https://doi.org/10.1234/tpd.2021.1.",
    },
    (CslStyle.MLA, CslLocale.EN): {
        "charmaz2008": "Charmaz, Kathy. “Grounded Theory.” Handbook of Emergent Methods, 2008, pp. 155–70.",
        "creswell2014": "Creswell, John W. Research Design. SAGE, 2014.",
        "dogru2026": "Doğru, Demirkan. Kod modelleri. 2026. Orta Doğu Teknik Üniversitesi, Master's thesis.",
        "vaswani2017": "Vaswani, Ashish. “Attention Is All You Need.” Advances in Neural Information Processing Systems, 2017, pp. 5998–6008.",
        "yilmaz2021": "Yılmaz, İsmail, and Ayşe Öztürk. “Yapay zekâ ile ölçek geliştirme.” Türk Psikoloji Dergisi, vol. 36, no. 2, 2021, pp. 45–67, https://doi.org/10.1234/tpd.2021.1.",
    },
    (CslStyle.CHICAGO_AUTHOR_DATE, CslLocale.TR): {
        "charmaz2008": "Charmaz, Kathy. 2008. “Grounded Theory”. İçinde Handbook of Emergent Methods.",
        "creswell2014": "Creswell, John W. 2014. Research Design. SAGE.",
        "dogru2026": "Doğru, Demirkan. 2026. “Kod modelleri”. Yüksek lisans tezi, Orta Doğu Teknik Üniversitesi.",
        "vaswani2017": "Vaswani, Ashish. 2017. “Attention Is All You Need”. Advances in Neural Information Processing Systems, 5998-6008.",
        "yilmaz2021": "Yılmaz, İsmail, ve Ayşe Öztürk. 2021. “Yapay zekâ ile ölçek geliştirme”. Türk Psikoloji Dergisi 36 (2): 45-67. https://doi.org/10.1234/tpd.2021.1.",
    },
    (CslStyle.CHICAGO_AUTHOR_DATE, CslLocale.EN): {
        "charmaz2008": "Charmaz, Kathy. 2008. “Grounded Theory.” In Handbook of Emergent Methods.",
        "creswell2014": "Creswell, John W. 2014. Research Design. SAGE.",
        "dogru2026": "Doğru, Demirkan. 2026. “Kod modelleri.” Master's thesis, Orta Doğu Teknik Üniversitesi.",
        "vaswani2017": "Vaswani, Ashish. 2017. “Attention Is All You Need.” Advances in Neural Information Processing Systems, 5998–6008.",
        "yilmaz2021": "Yılmaz, İsmail, and Ayşe Öztürk. 2021. “Yapay zekâ ile ölçek geliştirme.” Türk Psikoloji Dergisi 36 (2): 45–67. https://doi.org/10.1234/tpd.2021.1.",
    },
    (CslStyle.CHICAGO_NOTES, CslLocale.TR): {
        "charmaz2008": "Charmaz, Kathy. “Grounded Theory”. İçinde Handbook of Emergent Methods. 2008.",
        "creswell2014": "Creswell, John W. Research Design. SAGE, 2014.",
        "dogru2026": "Doğru, Demirkan. “Kod modelleri”. Yüksek lisans tezi, Orta Doğu Teknik Üniversitesi, 2026.",
        "vaswani2017": "Vaswani, Ashish. “Attention Is All You Need”. Advances in Neural Information Processing Systems, 2017, 5998-6008.",
        "yilmaz2021": "Yılmaz, İsmail, ve Ayşe Öztürk. “Yapay zekâ ile ölçek geliştirme”. Türk Psikoloji Dergisi 36, sy. 2 (2021): 45-67. https://doi.org/10.1234/tpd.2021.1.",
    },
    (CslStyle.CHICAGO_NOTES, CslLocale.EN): {
        "charmaz2008": "Charmaz, Kathy. “Grounded Theory.” In Handbook of Emergent Methods. 2008.",
        "creswell2014": "Creswell, John W. Research Design. SAGE, 2014.",
        "dogru2026": "Doğru, Demirkan. “Kod modelleri.” Master's thesis, Orta Doğu Teknik Üniversitesi, 2026.",
        "vaswani2017": "Vaswani, Ashish. “Attention Is All You Need.” Advances in Neural Information Processing Systems, 2017, 5998–6008.",
        "yilmaz2021": "Yılmaz, İsmail, and Ayşe Öztürk. “Yapay zekâ ile ölçek geliştirme.” Türk Psikoloji Dergisi 36, no. 2 (2021): 45–67. https://doi.org/10.1234/tpd.2021.1.",
    },
    (CslStyle.VANCOUVER, CslLocale.TR): {
        "yilmaz2021": "1. Yılmaz İ, Öztürk A. Yapay zekâ ile ölçek geliştirme. Türk Psikoloji Dergisi. 2021;36(2):45-67. doi:10.1234/tpd.2021.1",
        "creswell2014": "2. Creswell JW. Research design. SAGE; 2014.",
        "charmaz2008": "3. Charmaz K. Grounded theory. İçinde: Handbook of emergent methods. 2008. s. 155-70.",
        "vaswani2017": "4. Vaswani A. Attention is all you need. İçinde: Advances in Neural Information Processing Systems. 2017. s. 5998-6008.",
        "dogru2026": "5. Doğru D. Kod modelleri [Yüksek lisans tezi]. Orta Doğu Teknik Üniversitesi; 2026.",
    },
    (CslStyle.VANCOUVER, CslLocale.EN): {
        "yilmaz2021": "1. Yılmaz İ, Öztürk A. Yapay zekâ ile ölçek geliştirme. Türk Psikoloji Dergisi. 2021;36(2):45–67. doi:10.1234/tpd.2021.1",
        "creswell2014": "2. Creswell JW. Research design. SAGE; 2014.",
        "charmaz2008": "3. Charmaz K. Grounded theory. In: Handbook of emergent methods. 2008. p. 155–70.",
        "vaswani2017": "4. Vaswani A. Attention is all you need. In: Advances in Neural Information Processing Systems. 2017. p. 5998–6008.",
        "dogru2026": "5. Doğru D. Kod modelleri [Master's thesis]. Orta Doğu Teknik Üniversitesi; 2026.",
    },
    (CslStyle.IEEE, CslLocale.TR): {
        "yilmaz2021": "[1] İ. Yılmaz ve A. Öztürk, “Yapay zekâ ile ölçek geliştirme”, Türk Psikoloji Dergisi, c. 36, sy. 2, ss. 45-67, 2021, doi: 10.1234/tpd.2021.1.",
        "creswell2014": "[2] J. W. Creswell, Research design. SAGE, 2014.",
        "charmaz2008": "[3] K. Charmaz, “Grounded theory”, içinde Handbook of emergent methods, 2008, ss. 155-170.",
        "vaswani2017": "[4] A. Vaswani, “Attention is all you need”, içinde Advances in Neural Information Processing Systems, 2017, ss. 5998-6008.",
        "dogru2026": "[5] D. Doğru, “Kod modelleri”, Yüksek lisans tezi, Orta Doğu Teknik Üniversitesi, 2026.",
    },
    (CslStyle.IEEE, CslLocale.EN): {
        "yilmaz2021": "[1] İ. Yılmaz and A. Öztürk, “Yapay zekâ ile ölçek geliştirme,” Türk Psikoloji Dergisi, vol. 36, no. 2, pp. 45–67, 2021, doi: 10.1234/tpd.2021.1.",
        "creswell2014": "[2] J. W. Creswell, Research design. SAGE, 2014.",
        "charmaz2008": "[3] K. Charmaz, “Grounded theory,” in Handbook of emergent methods, 2008, pp. 155–170.",
        "vaswani2017": "[4] A. Vaswani, “Attention is all you need,” in Advances in Neural Information Processing Systems, 2017, pp. 5998–6008.",
        "dogru2026": "[5] D. Doğru, “Kod modelleri,” Master's thesis, Orta Doğu Teknik Üniversitesi, 2026.",
    },
}


@pytest.mark.parametrize(("style", "locale"), list(EXPECTED))
def test_each_style_renders_every_kind_of_work(style: CslStyle, locale: CslLocale) -> None:
    rendered = render(style, locale, SAMPLES)

    assert {entry.citekey: entry.text for entry in rendered} == EXPECTED[style, locale]
    assert [entry.citekey for entry in rendered] == list(EXPECTED[style, locale])


def test_html_keeps_the_style_formatting_and_escapes_text() -> None:
    paper = _paper("a2020", "Q&A <tags>", [("Kim", "Jo")], 2020, "Journal", VenueType.JOURNAL)

    (entry,) = render(CslStyle.APA, CslLocale.EN, [paper])

    assert entry.html == "Kim, J. (2020). Q&amp;A &lt;tags&gt;. <i>Journal</i>."
    assert entry.text == "Kim, J. (2020). Q&A <tags>. Journal."


def test_a_doctoral_thesis_and_an_unknown_degree() -> None:
    doctoral = _paper(
        "a2020",
        "Tez",
        [("Kaya", "Ali")],
        2020,
        "Ankara Üniversitesi",
        VenueType.THESIS,
        thesis_type=ThesisType.DOCTORAL,
    )
    unknown = _paper(
        "b2020", "Tez", [("Kaya", "Bora")], 2020, "Ankara Üniversitesi", VenueType.THESIS
    )

    tr = render(CslStyle.APA, CslLocale.TR, [doctoral, unknown])
    en = render(CslStyle.APA, CslLocale.EN, [doctoral])

    assert tr[0].text == "Kaya, A. (2020). Tez [Doktora tezi]. Ankara Üniversitesi."
    assert tr[1].text == "Kaya, B. (2020). Tez. Ankara Üniversitesi."
    assert en[0].text == "Kaya, A. (2020). Tez [Doctoral dissertation]. Ankara Üniversitesi."


def test_turkish_casing_is_for_turkish_terms_and_items_only() -> None:
    english = _paper(
        "a2020",
        "the art of insight",
        [("Kim", "Jo")],
        2020,
        "In Press",
        VenueType.BOOK,
        language="en",
    )

    (entry,) = render(CslStyle.MLA, CslLocale.TR, [english])

    # English title case under a Turkish locale: "Insight", not "İnsight".
    assert entry.text == "Kim, Jo. The Art of Insight. In Press, 2020."


def test_an_unknown_language_is_the_bibliography_language() -> None:
    paper = _paper("a2020", "eğitim ve bilim", [("Kim", "Jo")], 2020, "Press", VenueType.BOOK)

    (tr,) = render(CslStyle.MLA, CslLocale.TR, [paper])
    (en,) = render(CslStyle.MLA, CslLocale.EN, [paper])

    # A Turkish list leaves the title as it is; an English one title-cases it (as English).
    assert tr.text == "Kim, Jo. eğitim ve bilim. Press, 2020."
    assert en.text == "Kim, Jo. Eğitim Ve Bilim. Press, 2020."


@pytest.mark.parametrize(
    ("display_name", "expected"),
    [
        # Search sources often give only the full name; the family name is the last word.
        ("Erdal Bay", "Bay, E."),
        ("Mehmet Nur Tuğluk", "Tuğluk, M. N."),
        # TR Dizin writes family names in capitals; a short one is still a family name.
        ("Osman KOÇ", "KOÇ, O."),
        # "Family, Given" as typed in BibTeX.
        ("Gençdoğan, Başaran", "Gençdoğan, B."),
        # A particle goes with the family name.
        ("Ludwig van Beethoven", "van Beethoven, L."),
    ],
)
def test_a_full_name_alone_is_split_into_family_and_given(display_name: str, expected: str) -> None:
    paper = _paper("a2020", "Title", [], 2020, "Journal", VenueType.JOURNAL)
    paper = replace(paper, authors=(ExportAuthor(display_name, None, None),))

    (entry,) = render(CslStyle.APA, CslLocale.EN, [paper])

    assert entry.text.startswith(f"{expected} (2020)."), entry.text


def test_a_one_word_name_stays_as_written() -> None:
    paper = _paper("a2020", "Title", [], 2020, "Journal", VenueType.JOURNAL)
    paper = replace(paper, authors=(ExportAuthor("UNESCO", None, None),))

    (entry,) = render(CslStyle.APA, CslLocale.EN, [paper])

    assert entry.text.startswith("UNESCO. (2020)."), entry.text


def test_no_papers_no_entries() -> None:
    assert render(CslStyle.IEEE, CslLocale.EN, []) == []


@pytest.fixture
def library(tmp_path: Path) -> Library:
    return open_library(tmp_path / "lib", create=True)


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(
        token=TOKEN, settings=Settings(), library=library, secret_store=MemorySecretStore()
    )
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


def _seed(library: Library) -> tuple[str, list[str]]:
    """A review with three records: one included at full text, one undecided there (maybe), one only
    past title-abstract screening."""
    with library.db.write_session() as session:
        papers = PaperService(session)
        added = [
            papers.add(
                title,
                identifiers={IdentifierScheme.DOI: f"10.1/{family.lower()}"},
                authors=[AuthorInput(f"Ayşe {family}", family=family, given="Ayşe")],
                year=2020,
                venue="Eğitim ve Bilim",
                venue_type=VenueType.JOURNAL,
            )
            for title, family in (("Birinci", "Akın"), ("İkinci", "Bal"), ("Üçüncü", "Can"))
        ]
        papers.keep([paper.id for paper in added])
        reviews = ReviewsRepository(session)
        review = reviews.add_review("SLR", method=ReviewMethod.PRISMA2020)
        for paper in added:
            reviews.add_record(review.id, paper.id, RecordOrigin.DATABASE, None)
        screening = ScreeningService(session)
        for paper in added:
            screening.decide(review.id, paper.id, ScreeningStage.TITLE_ABSTRACT, Decision.INCLUDE)
        screening.decide(review.id, added[0].id, ScreeningStage.FULL_TEXT, Decision.INCLUDE)
        screening.decide(review.id, added[1].id, ScreeningStage.FULL_TEXT, Decision.MAYBE)
        return review.id, [paper.id for paper in added]


def test_a_review_gives_the_bibliography_of_its_included_studies(
    client: TestClient, library: Library
) -> None:
    review_id, _ = _seed(library)

    result = client.post(
        "/export/bibliography", json={"review_id": review_id, "style": "apa", "locale": "tr-TR"}
    ).json()

    assert result["count"] == 1
    assert result["text"] == "Akın, A. (2020). Birinci. Eğitim ve Bilim. https://doi.org/10.1/akın"
    assert result["html"] == (
        "<p>Akın, A. (2020). Birinci. <i>Eğitim ve Bilim</i>. https://doi.org/10.1/akın</p>"
    )


def test_chosen_papers_a_collection_and_the_whole_library(
    client: TestClient, library: Library
) -> None:
    _, ids = _seed(library)
    collection = client.post("/collections", json={"name": "Okunacak"}).json()
    client.post(f"/collections/{collection['id']}/papers", json={"paper_ids": ids[1:]})

    def families(body: dict[str, object]) -> list[str]:
        result = client.post("/export/bibliography", json={"style": "ieee", **body}).json()
        return [entry["text"].split(",")[0] for entry in result["entries"]]

    assert families({"paper_ids": [ids[2], ids[0]]}) == ["[1] A. Akın", "[2] A. Can"]
    assert families({"collection_id": collection["id"]}) == ["[1] A. Bal", "[2] A. Can"]
    assert len(families({})) == 3


def test_one_scope_and_known_styles(client: TestClient) -> None:
    both = client.post("/export/bibliography", json={"review_id": "r", "paper_ids": ["p"]})
    missing = client.post("/export/bibliography", json={"review_id": "nope"})
    style = client.post("/export/bibliography", json={"style": "harvard"})

    assert both.json()["error"]["code"] == "export.one_scope"
    assert missing.json()["error"]["code"] == "review.not_found"
    assert style.status_code == 422
