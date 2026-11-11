"""Find an open-access PDF for a paper and download it, as a background job (plan, Task 17).

Where a free copy may be, in order:

1. arXiv, when the paper has an arXiv id: the preprint is always free.
2. Unpaywall, when it has a DOI: its best open location, then the others. Unpaywall asks for an
   e-mail address on every request (the one in Settings).
3. The open-access link a search source gave (`paper.oa_url`).

A candidate that answers with a web page instead of a PDF (a landing page, a login wall) is
skipped. The first real PDF is stored like a dropped file (Task 16) and inspected in turn.
"""

import asyncio
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from tez.core.db import Database
from tez.core.errors import ErrorCode, TezError
from tez.modules.files import service as files_service
from tez.modules.files import storage
from tez.modules.files.repository import FilesRepository
from tez.modules.files.schemas import MAX_PDF_BYTES, PdfAdded
from tez.modules.jobs import service as jobs_service
from tez.modules.jobs.registry import JobContext, JobFailed
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.paper_service import PaperService
from tez.modules.settings import service as settings_service
from tez.shared.http import HttpClient, SourcePolicy

logger = logging.getLogger(__name__)

FETCH_JOB = "pdf.fetch_open_access"

UNPAYWALL_API = "https://api.unpaywall.org/v2/"
ARXIV_PDF = "https://arxiv.org/pdf/"
# Unpaywall allows 100,000 calls a day; arXiv asks for one request every three seconds.
UNPAYWALL = SourcePolicy("unpaywall", requests_per_second=5.0, max_attempts=3)
ARXIV = SourcePolicy("arxiv", requests_per_second=1 / 3, timeout_seconds=120.0, max_attempts=1)
# Repositories and publishers: many hosts, so one modest shared rate.
HOSTS = SourcePolicy("oa_host", requests_per_second=1.0, timeout_seconds=120.0, max_attempts=1)


@dataclass(frozen=True)
class Candidate:
    url: str
    # Where the link came from, kept on the attachment: arxiv, unpaywall or the search source.
    source: str


@dataclass(frozen=True)
class PaperRef:
    paper_id: str
    doi: str | None
    arxiv_id: str | None
    oa_url: str | None
    title: str


class OpenAccess(Protocol):
    """Finds and fetches files. The real one is on the network; tests use a fake."""

    async def unpaywall(self, doi: str) -> list[Candidate]: ...

    async def download(
        self, candidate: Candidate, on_progress: Callable[[int, int | None], None]
    ) -> bytes: ...


class HttpOpenAccess:
    def __init__(self, http: HttpClient, email: str) -> None:
        self._http = http
        self._email = email

    async def unpaywall(self, doi: str) -> list[Candidate]:
        response = await self._http.get(
            UNPAYWALL, UNPAYWALL_API + doi, params={"email": self._email}, cache_ttl=86400
        )
        return unpaywall_candidates(cast(object, response.json()))

    async def download(
        self, candidate: Candidate, on_progress: Callable[[int, int | None], None]
    ) -> bytes:
        policy = ARXIV if candidate.source == "arxiv" else HOSTS
        found = await self._http.download(
            policy, candidate.url, max_bytes=MAX_PDF_BYTES, on_progress=on_progress
        )
        return found.content


def unpaywall_candidates(document: object) -> list[Candidate]:
    """PDF links from an Unpaywall answer: the best location first, no repeats."""
    if not isinstance(document, dict):
        return []
    record = cast(dict[str, Any], document)
    locations: list[Any] = [record.get("best_oa_location")]
    others = record.get("oa_locations")
    if isinstance(others, list):
        locations += cast(list[Any], others)
    urls: list[str] = []
    for location in locations:
        if not isinstance(location, dict):
            continue
        url = cast(dict[str, Any], location).get("url_for_pdf")
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in urls:
            urls.append(url)
    return [Candidate(url, "unpaywall") for url in urls]


def _file_name(paper: PaperRef) -> str:
    if paper.arxiv_id:
        return f"arXiv-{paper.arxiv_id.replace('/', '_')}.pdf"
    if paper.doi:
        return re.sub(r"[^\w.-]+", "_", paper.doi) + ".pdf"
    words = re.sub(r"[^\w]+", " ", paper.title).split()[:8]
    return ("_".join(words) or "paper") + ".pdf"


def read_paper(db: Database, paper_id: str) -> PaperRef | None:
    with db.session() as session:
        card = PaperService(session).cards([paper_id]).get(paper_id)
        if card is None:
            return None
        return PaperRef(
            paper_id=paper_id,
            doi=card.identifiers.get(IdentifierScheme.DOI),
            arxiv_id=card.identifiers.get(IdentifierScheme.ARXIV),
            oa_url=card.paper.oa_url,
            title=card.paper.title,
        )


def has_pdf(db: Database, paper_id: str) -> bool:
    with db.session() as session:
        return bool(FilesRepository(session).for_paper(paper_id))


async def find_and_store(
    db: Database,
    paper: PaperRef,
    access: OpenAccess | None,
    *,
    has_email: bool,
    report: Callable[[float], None],
) -> PdfAdded:
    """Try each candidate in turn; raises `JobFailed` when none gives a PDF."""
    candidates: list[Candidate] = []
    if paper.arxiv_id:
        candidates.append(Candidate(ARXIV_PDF + paper.arxiv_id, "arxiv"))
    transient: TezError | None = None
    if paper.doi and access is not None and has_email:
        try:
            candidates += await access.unpaywall(paper.doi)
        except TezError as error:
            # Unpaywall has no record of a DOI it never saw (404): no candidates, not a fault.
            if error.code is not ErrorCode.SOURCE_REJECTED:
                transient = error
    if paper.oa_url and all(c.url != paper.oa_url for c in candidates):
        candidates.append(Candidate(paper.oa_url, "search"))

    if access is not None:
        for index, candidate in enumerate(candidates):
            share = 1 / len(candidates)

            def progress(done: int, total: int | None, index: int = index, share: float = share):
                fraction = done / total if total else 0.5
                report(min(index * share + fraction * share, 0.99))

            try:
                data = await access.download(candidate, progress)
            except TezError as error:
                logger.info("oa candidate failed", extra={"url": candidate.url, "code": error.code})
                if error.code is not ErrorCode.SOURCE_REJECTED:
                    transient = error
                continue
            if not storage.looks_like_pdf(data):
                logger.info("oa candidate is not a pdf", extra={"url": candidate.url})
                continue
            return files_service.add_pdf(
                db,
                db.path.parent,
                data,
                _file_name(paper),
                paper_id=paper.paper_id,
                source=candidate.source,
            )

    if transient is not None:
        # The network or a host failed: worth another attempt later.
        raise JobFailed(transient.code.value, transient.params, retry=True)
    if paper.doi and not has_email and not candidates:
        raise JobFailed(ErrorCode.SOURCE_EMAIL_REQUIRED.value, {"source": "unpaywall"})
    raise JobFailed(ErrorCode.PDF_NO_OPEN_ACCESS.value, {"tried": len(candidates)})


def fetch_open_access(payload: dict[str, object], ctx: JobContext) -> None:
    """The `pdf.fetch_open_access` job."""
    paper_id = str(payload["paper_id"])
    paper = read_paper(ctx.db, paper_id)
    if paper is None:
        raise JobFailed(ErrorCode.PAPER_NOT_FOUND.value, {"paper_ids": [paper_id]})
    if has_pdf(ctx.db, paper_id):
        ctx.report(1.0)
        return
    email = settings_service.read_settings(ctx.db).sources_email

    async def run() -> None:
        async with HttpClient(cache_path=ctx.library_path / ".tez" / "http-cache.sqlite") as http:
            access = HttpOpenAccess(http, email or "")
            await find_and_store(ctx.db, paper, access, has_email=bool(email), report=ctx.report)

    asyncio.run(run())
    ctx.report(1.0)


@dataclass(frozen=True)
class QueueResult:
    job_ids: list[str]
    already_have_pdf: int
    no_source: int


def queue_fetches(db: Database, paper_ids: Sequence[str]) -> QueueResult:
    """One job per paper that has no PDF and has somewhere to look for one.

    Asking for a paper's PDF keeps it: the papers are put in the library as well.
    """
    job_ids: list[str] = []
    have = no_source = 0
    with db.write_session() as session:
        papers = PaperService(session)
        wanted = list(dict.fromkeys(paper_ids))
        cards = papers.cards(wanted)
        if missing := [p for p in wanted if p not in cards]:
            raise TezError(ErrorCode.PAPER_NOT_FOUND, {"paper_ids": missing}, status=404)
        files = FilesRepository(session)
        for paper_id in wanted:
            card = cards[paper_id]
            if files.for_paper(paper_id):
                have += 1
                continue
            ids = card.identifiers
            searchable = IdentifierScheme.DOI in ids or IdentifierScheme.ARXIV in ids
            if not (searchable or card.paper.oa_url):
                no_source += 1
                continue
            job_ids.append(
                jobs_service.enqueue(
                    session, FETCH_JOB, {"paper_id": paper_id}, dedupe_key=f"oa:{paper_id}"
                )
            )
        papers.keep(wanted)
    return QueueResult(job_ids=job_ids, already_have_pdf=have, no_source=no_source)
