"""A demo library of made-up papers, for trying the app and for performance checks (Task 19).

    uv run --project backend python -m tez.devtools.demo "C:/TEz Demo" --papers 2000
    uv run --project backend python -m tez.devtools.demo "C:/TEz Demo" --review

With `--review` the library also gets a demo review, screened and tabulated (Task 57).

Everything is generated from fixed word lists with a fixed seed, so the same command gives the
same library. Titles, names and DOIs are fictional (DOIs use the 10.5555 test prefix).
"""

import argparse
import random
import sys
from pathlib import Path

from tez.core.db import Database
from tez.devtools.demo_review import make_review
from tez.modules.library.models import IdentifierScheme, ReadingStatus, VenueType
from tez.modules.library.paper_service import PaperService
from tez.modules.library.repository import AuthorInput, LibraryRepository
from tez.modules.library.service import open_library

_SUBJECTS = [
    "Code Review",
    "Large Language Models",
    "Program Repair",
    "Test Generation",
    "Static Analysis",
    "Vulnerability Detection",
    "Code Summarization",
    "Refactoring",
    "Technical Debt",
    "Continuous Integration",
    "Pull Requests",
    "Code Smells",
    "Software Documentation",
    "Commit Messages",
    "Defect Prediction",
    "Code Search",
]
_FORMS = [
    "{a} for {b}: An Empirical Study",
    "Towards {a} in {b}",
    "On the Use of {a} for {b}",
    "{a} Meets {b}",
    "A Systematic Literature Review of {a} in {b}",
    "Evaluating {a} for {b} in Industrial Settings",
    "{a} and {b}: A Replication",
    "Can {a} Replace Human {b}?",
    "Understanding {b} through {a}",
]
_GIVEN = [
    "Ayşe",
    "Mehmet",
    "Zeynep",
    "İlker",
    "Elif",
    "Işıl",
    "Can",
    "Deniz",
    "Jane",
    "Wei",
    "Maria",
    "John",
    "Ahmet",
    "Selin",
    "Ömer",
    "Priya",
    "Lukas",
    "Yuki",
    "Fatma",
    "Emre",
]
_FAMILY = [
    "Yılmaz",
    "Kaya",
    "Şahin",
    "Çelik",
    "Öztürk",
    "Doğan",
    "Arslan",
    "Güneş",
    "Smith",
    "Chen",
    "Garcia",
    "Kim",
    "Müller",
    "Rossi",
    "Nakamura",
    "Patel",
    "Aydın",
    "Koç",
    "Erdoğan",
    "Taş",
]
_VENUES = [
    ("IEEE Transactions on Software Engineering", VenueType.JOURNAL),
    ("Empirical Software Engineering", VenueType.JOURNAL),
    ("ICSE", VenueType.CONFERENCE),
    ("ESEC/FSE", VenueType.CONFERENCE),
    ("MSR", VenueType.CONFERENCE),
    ("ASE", VenueType.CONFERENCE),
    ("arXiv", VenueType.PREPRINT),
    ("Information and Software Technology", VenueType.JOURNAL),
]
_SENTENCES = [
    "We study how {a} affects {b} in open-source and industrial projects.",
    "Our results show that {a} improves precision but misses semantic defects.",
    "We collected {n} pull requests from {m} repositories.",
    "Practitioners reported that {b} remains costly despite automation.",
    "We discuss threats to validity and outline directions for future work.",
]
_COLLECTIONS = {"Tez": ["Arka Plan", "Yöntem", "Karşılaştırma"], "Okuma Listesi": []}
_TAGS = [
    ("derin-öğrenme", "purple"),
    ("benchmark", "blue"),
    ("ampirik-çalışma", "green"),
    ("anket", "yellow"),
]


def make_library(path: Path, papers: int, *, seed: int = 2026, review: bool = False) -> None:
    rng = random.Random(seed)
    library = open_library(path, create=True)
    try:
        _fill(library.db, papers, rng)
        if review:
            make_review(library.db, library.path)
    finally:
        library.close()


def _fill(db: Database, count: int, rng: random.Random) -> None:
    with db.write_session() as session:
        service = PaperService(session)
        repository = LibraryRepository(session)
        ids: list[str] = []
        for index in range(count):
            a, b = rng.sample(_SUBJECTS, 2)
            title = rng.choice(_FORMS).format(a=a, b=b)
            venue, venue_type = rng.choice(_VENUES)
            authors = [
                AuthorInput(display_name=f"{g} {f}", family=f, given=g)
                for g, f in zip(
                    rng.sample(_GIVEN, rng.randint(1, 4)),
                    rng.sample(_FAMILY, 4),
                    strict=False,
                )
            ]
            abstract = " ".join(
                s.format(a=a.lower(), b=b.lower(), n=rng.randint(100, 9000), m=rng.randint(5, 90))
                for s in rng.sample(_SENTENCES, 4)
            )
            paper = service.add(
                title,
                identifiers={IdentifierScheme.DOI: f"10.5555/tez-demo.{index:05d}"},
                authors=authors,
                year=rng.randint(2015, 2026),
                venue=venue,
                venue_type=venue_type,
                abstract=abstract,
                citation_count=rng.randint(0, 400),
            )
            paper.reading_status = rng.choice(list(ReadingStatus))
            ids.append(paper.id)
        service.keep(ids)
        for parent, children in _COLLECTIONS.items():
            top = repository.add_collection(parent)
            for paper_id in rng.sample(ids, min(len(ids), 400)):
                repository.add_to_collection(top.id, paper_id)
            for child in children:
                sub = repository.add_collection(child, parent_id=top.id)
                for paper_id in rng.sample(ids, min(len(ids), 120)):
                    repository.add_to_collection(sub.id, paper_id)
        for name, color in _TAGS:
            tag = repository.add_tag(name, color=color)
            for paper_id in rng.sample(ids, min(len(ids), 150)):
                repository.tag_paper(paper_id, tag.id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Make a demo TEz library of fictional papers.")
    parser.add_argument("folder", type=Path, help="a new or empty folder")
    parser.add_argument("--papers", type=int, default=2000)
    parser.add_argument(
        "--review", action="store_true", help="add a demo review, screened and tabulated"
    )
    args = parser.parse_args(argv)
    make_library(args.folder, args.papers, review=args.review)
    with_review = " and a demo review" if args.review else ""
    print(f"demo library with {args.papers} papers{with_review}: {args.folder.absolute()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
