"""A demo review on top of the demo library: searched, screened, read and tabulated (Task 57).

    uv run --project backend python -m tez.devtools.demo "C:/TEz Demo" --review

Two database searches (exports logged as search runs, one record found by both), title-abstract
and full-text decisions with reasons, a report not retrieved, small PDFs written here, and a
literature matrix whose findings are backed by passages of those PDFs. Everything is fictional:
names are made up and DOIs use the 10.5555 test prefix.
"""

import base64
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from tez.core.db import Database
from tez.modules.anchors import service as anchors
from tez.modules.anchors.schemas import AnchorCreate
from tez.modules.files import service as files
from tez.modules.importers import service as importers
from tez.modules.importers.schemas import ImportLog, ImportRequest
from tez.modules.matrix import service as matrix
from tez.modules.matrix.schemas import ColumnCreate
from tez.modules.matrix.values import DataType
from tez.modules.reviews import service as reviews
from tez.modules.reviews.models import CriterionKind, Decision, ScreeningStage
from tez.modules.reviews.schemas import CriterionCreate, ReviewCreate
from tez.modules.screening import service as screening
from tez.modules.screening.schemas import QueueFilter

TITLE = "Demo: LLM assistants in code review"


@dataclass(frozen=True)
class _Study:
    title: str
    author: str
    year: int
    abstract: str
    # Title-abstract: None includes; else the exclusion reason's code.
    ta_reason: str | None = None
    # Full text: None includes, "E3" excludes, "missing" is a report not retrieved.
    ft: str | None = None
    # What the matrix holds for an included study: method, sample size, finding.
    method: str = ""
    sample: int | None = None
    finding: str = ""


_STUDIES = [
    _Study(
        "Reviewer Bots in Industrial Code Review: A Field Study",
        "Yılmaz, Ayşe",
        2023,
        "We deployed an LLM reviewer in two companies and followed 1,200 pull requests.",
        method="Field study",
        sample=1200,
        finding="Bot comments were resolved in 61% of cases, mostly style and naming issues.",
    ),
    _Study(
        "Do Developers Trust Generated Review Comments? A Survey",
        "Kaya, Mehmet",
        2024,
        "A survey of 340 developers on how they judge comments written by language models.",
        method="Survey",
        sample=340,
        finding="Developers trusted generated comments less when no line of code was cited.",
    ),
    _Study(
        "Automated Review of Security Defects with Large Language Models",
        "Demir, Zeynep",
        2024,
        "We evaluate four models on 800 known vulnerable changes from open-source projects.",
        method="Benchmark",
        sample=800,
        finding="The best model found 47% of the injected defects, with many false alarms.",
    ),
    _Study(
        "Review Latency Before and After an LLM Assistant",
        "Öztürk, İlker",
        2025,
        "A before-after comparison of time to first review in a large open-source project.",
        method="Quasi-experiment",
        sample=5400,
        finding="Median time to first review fell from 19 to 7 hours after the assistant.",
    ),
    _Study(
        "Explaining Code Changes to Reviewers with Language Models",
        "Wei, Chen",
        2023,
        "A controlled experiment with 48 students reviewing changes with generated summaries.",
        method="Controlled experiment",
        sample=48,
        finding="Summaries shortened reviews without lowering the defects found.",
    ),
    _Study(
        "Code Review Comments Classified by a Fine-Tuned Model",
        "García, Maria",
        2022,
        "A fine-tuned classifier for review comments, evaluated on three projects.",
        ft="E3",
    ),
    _Study(
        "An Assistant for Review Checklists in Safety-Critical Software",
        "Şahin, Deniz",
        2025,
        "An LLM that fills review checklists in an automotive supplier.",
        ft="missing",
    ),
    _Study(
        "Pair Review with a Chat Model: An Exploratory Study",
        "Çelik, Elif",
        2024,
        "Twelve developers reviewed code together with a chat model and were interviewed.",
        method="Interview study",
        sample=12,
        finding="Developers used the model to question their own reading, not to decide.",
    ),
    _Study(
        "The Future of Code Review: An Editorial",
        "Doe, Jane",
        2024,
        "An editorial on where code review is heading.",
        ta_reason="E1",
    ),
    _Study(
        "Compiler Optimisation with Reinforcement Learning",
        "Arslan, Can",
        2023,
        "Reinforcement learning chooses compiler passes for embedded targets.",
        ta_reason="E2",
    ),
    _Study(
        "Code Review Practices at a Bank: Interviews",
        "Işık, Işıl",
        2021,
        "Interviews on review practices, with no automated assistance.",
        ta_reason="E2",
    ),
]
# Found by both searches: the second export repeats it, the review keeps one record.
_BOTH = _STUDIES[0]


def _ris(studies: list[_Study]) -> bytes:
    lines: list[str] = []
    for study in studies:
        index = _STUDIES.index(study)
        lines += [
            "TY  - JOUR",
            f"TI  - {study.title}",
            f"AU  - {study.author}",
            f"PY  - {study.year}",
            f"AB  - {study.abstract}",
            f"DO  - 10.5555/tez-demo-review.{index:02d}",
            "ER  - ",
            "",
        ]
    return "\n".join(lines).encode()


def _pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf(study: _Study) -> tuple[bytes, float]:
    """A three-page report; its finding is the first line of page 2, at the returned height."""
    pages = [
        [study.title, study.author, "Abstract", study.abstract],
        [study.finding, f"Method: {study.method}.", "Threats to validity are discussed."],
        ["References", "[1] A fictional reference, 2020."],
    ]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids: list[int] = []
    for lines in pages:
        shown = " ".join(
            f"BT /F1 11 Tf 72 {720 - 18 * n} Td ({_pdf_text(line)}) Tj ET"
            for n, line in enumerate(lines)
        ).encode()
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(shown), shown))
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % len(objects)
        )
        kids.append(len(objects))
    refs = " ".join(f"{n} 0 R" for n in kids)
    objects[1] = f"<< /Type /Pages /Kids [{refs}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out), 720.0


def _import(
    db: Database,
    library: Path,
    review_id: str,
    name: str,
    source: str,
    query: str,
    studies: list[_Study],
    day: date,
) -> None:
    importers.run_import(
        db,
        library,
        ImportRequest(
            file_name=name,
            content_base64=base64.b64encode(_ris(studies)).decode(),
            review_id=review_id,
            log=ImportLog(source=source, searched_at=day, query=query),
            add_to_review=True,
        ),
    )


def make_review(db: Database, library: Path) -> str:
    """Add the demo review to an open library; returns its id."""
    review = reviews.create_review(
        db,
        ReviewCreate(
            title=TITLE,
            research_questions=[
                "How are LLM assistants used in code review?",
                "What do they change in review speed and quality?",
            ],
        ),
    )
    reasons: dict[str, str] = {}
    for kind, text, stage in (
        (CriterionKind.INCLUSION, "An empirical study of an LLM used in code review", None),
        (CriterionKind.EXCLUSION, "Not a study (editorial, opinion)", None),
        (CriterionKind.EXCLUSION, "Not about code review", None),
        (CriterionKind.EXCLUSION, "No evaluation of the assistant", ScreeningStage.FULL_TEXT),
    ):
        criterion = reviews.add_criterion(
            db, review.id, CriterionCreate(kind=kind, text=text, stage=stage)
        )
        reasons[criterion.code] = criterion.id

    query = '("large language model" OR LLM) AND "code review"'
    _import(db, library, review.id, "scopus.ris", "Scopus", query, _STUDIES[:8], date(2026, 10, 2))
    rest = [_BOTH, *_STUDIES[8:]]
    _import(db, library, review.id, "ieee.ris", "IEEE Xplore", query, rest, date(2026, 10, 2))

    queue = screening.queue_view(db, review.id, ScreeningStage.TITLE_ABSTRACT, QueueFilter.ALL)
    paper_of = {item.title: item.paper_id for item in queue.items}

    def decide(stage: ScreeningStage, study: _Study, decision: Decision, code: str | None) -> None:
        screening.decide(
            db,
            review.id,
            stage,
            paper_of[study.title],
            decision,
            criterion_id=reasons[code] if code else None,
            note=None,
        )

    for study in _STUDIES:
        if study.ta_reason:
            decide(ScreeningStage.TITLE_ABSTRACT, study, Decision.EXCLUDE, study.ta_reason)
        else:
            decide(ScreeningStage.TITLE_ABSTRACT, study, Decision.INCLUDE, None)

    sheet = matrix.create_matrix(db, review.id, "Data extraction")
    method = matrix.add_column(db, sheet.id, ColumnCreate(name="Method"))
    sample = matrix.add_column(db, sheet.id, ColumnCreate(name="Sample", data_type=DataType.NUMBER))
    finding = matrix.add_column(db, sheet.id, ColumnCreate(name="Main finding"))
    for study in _STUDIES:
        if study.ta_reason:
            continue
        if study.ft == "missing":
            decide(ScreeningStage.FULL_TEXT, study, Decision.NOT_RETRIEVED, None)
            continue
        data, top = _pdf(study)
        index = _STUDIES.index(study)
        added = files.add_pdf(
            db, library, data, f"demo-{index:02d}.pdf", paper_id=paper_of[study.title]
        )
        if study.ft:
            decide(ScreeningStage.FULL_TEXT, study, Decision.EXCLUDE, study.ft)
            continue
        decide(ScreeningStage.FULL_TEXT, study, Decision.INCLUDE, None)
        paper_id = paper_of[study.title]
        matrix.put_cell(db, sheet.id, paper_id, method.id, study.method)
        matrix.put_cell(db, sheet.id, paper_id, sample.id, study.sample)
        # The finding comes from page 2 of the PDF: a passage that backs the cell.
        width = 5.5 * len(study.finding)
        anchor = anchors.add(
            db,
            added.attachment_id,
            AnchorCreate(page=2, rects=[[72, top - 3, 72 + width, top + 9]], quote=study.finding),
        )
        matrix.link_evidence(db, sheet.id, paper_id, finding.id, anchor.id, fill=True)
    return review.id
