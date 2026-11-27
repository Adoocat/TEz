"""Task 57: the demo review is a whole review, its PRISMA counts derived from what was done."""

from pathlib import Path

from tez.devtools.demo import main
from tez.devtools.demo_review import TITLE
from tez.modules.library.service import open_library
from tez.modules.matrix import service as matrix
from tez.modules.prisma import service as prisma
from tez.modules.reviews import service as reviews


def test_the_demo_review_is_searched_screened_and_tabulated(tmp_path: Path) -> None:
    folder = tmp_path / "demo"
    assert main([str(folder), "--papers", "20", "--review"]) == 0

    library = open_library(folder)
    try:
        review = next(r for r in reviews.list_reviews(library.db) if r.title == TITLE)
        counts = prisma.counts(library.db, review.id).databases
        # Two exports: 8 + 4 records, one of them found by both.
        assert [(s.source, s.identified) for s in counts.sources] == [
            ("Scopus", 8),
            ("IEEE Xplore", 4),
        ]
        assert counts.duplicates == 1
        assert (counts.screened, counts.excluded) == (11, 3)
        assert (counts.sought, counts.not_retrieved, counts.assessed) == (8, 1, 7)
        assert [(r.code, r.count) for r in counts.excluded_reports] == [("E3", 1)]
        assert counts.included == 6

        [summary] = matrix.list_matrices(library.db, review.id)
        sheet = matrix.get_matrix(library.db, summary.id)
        assert len(sheet.rows) == 6
        # Method, sample and finding for each; every finding rests on a passage of its PDF.
        assert sheet.coverage.filled == 18
        assert sheet.coverage.sourced == 6
    finally:
        library.close()
