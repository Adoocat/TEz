"""The GROBID adapter (Task 56, ADR 0037): a PDF in, TEI XML out.

GROBID is optional and runs outside TEz (Docker, or a lab machine reached through a tunnel).
Its address must be on this computer (rule 1: user data stays here). Tests use a fake that
answers with a recorded response; nothing in the test suite reaches the network.
"""

from collections.abc import Callable
from typing import Protocol

import httpx2

from tez.core.errors import ErrorCode, TezError

# Seconds; a long paper can take GROBID a minute on a laptop.
TIMEOUT = 180.0


class GrobidClient(Protocol):
    def process(self, pdf: bytes) -> str:
        """The paper's TEI XML, with coordinates for headings and references."""
        ...


class HttpGrobid:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")

    def process(self, pdf: bytes) -> str:
        try:
            response = httpx2.post(
                f"{self.url}/api/processFulltextDocument",
                files={"input": ("paper.pdf", pdf, "application/pdf")},
                data={
                    "teiCoordinates": ["head", "biblStruct"],
                    "includeRawCitations": "1",
                    "consolidateCitations": "0",
                },
                timeout=TIMEOUT,
            )
        except httpx2.HTTPError as error:
            raise TezError(ErrorCode.GROBID_UNREACHABLE, {"url": self.url}) from error
        if response.status_code != 200:
            raise TezError(ErrorCode.GROBID_FAILED, {"status": response.status_code})
        return response.text


# Replaced in tests by a fake that answers from a recorded response.
client_for: Callable[[str], GrobidClient] = HttpGrobid
