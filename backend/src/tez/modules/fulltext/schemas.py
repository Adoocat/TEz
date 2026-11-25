from pydantic import BaseModel, ConfigDict, Field


class FulltextQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=1, max_length=500)
    # Look only in these papers (the list the user is looking at); None looks everywhere.
    paper_ids: list[str] | None = Field(default=None, max_length=20_000)
    limit: int = Field(default=30, ge=1, le=200)


class SnippetPart(BaseModel):
    text: str
    # A word of the query.
    hit: bool


class FulltextPage(BaseModel):
    attachment_id: str
    # Counts from 1, like the reader's address.
    page: int
    snippet: list[SnippetPart]


class FulltextPaper(BaseModel):
    paper_id: str
    title: str
    first_author: str | None
    author_count: int
    year: int | None
    # How many of the paper's pages match; `pages` holds the best few of them.
    page_hits: int
    pages: list[FulltextPage]


class FulltextResults(BaseModel):
    papers: list[FulltextPaper]
    # Papers with a match; more than `papers` when the limit cut the list.
    total_papers: int
    total_pages: int
    # Only the best pages were looked at; the totals are lower bounds.
    truncated: bool
    elapsed_ms: float
