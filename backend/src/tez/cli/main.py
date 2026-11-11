"""`tez`: search, import, add and export from a terminal (plan, Task 23).

    tez search "code review" AND LLM --sources openalex,s2 --review "SLR"
    tez import scopus.ris --source Scopus --searched-at 2026-11-01
    tez add papers/*.pdf --collection Tez
    tez export --format bibtex --review "SLR" -o refs.bib

Exit codes: 0 done, 1 failed, 2 partly done (a source failed, entries were skipped, some files
could not be added). With `--json` the output is one JSON document with English field names;
human output follows `--lang`, `TEZ_LANG` or the system language.
"""

import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from tez.cli.access import Access, CliFailure, connect, to_json
from tez.cli.i18n import Messages, detect_language, translate_click
from tez.core.config import Settings as AppSettings
from tez.core.errors import ErrorCode, TezError
from tez.core.logging import configure_logging
from tez.modules.importers.schemas import ImportLog, ImportRequest
from tez.modules.reviews.schemas import ReviewView
from tez.modules.search.models import RunStatus
from tez.modules.search.providers.base import SearchRequest
from tez.modules.search.providers.registry import SOURCE_NAMES
from tez.modules.search.schemas import SourceProgress, SourceState
from tez.shared.text import fold

Say = Callable[[str], None]

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_PARTIAL = 2

_SOURCE_ALIASES = {
    "oa": "openalex",
    "s2": "semantic_scholar",
    "semanticscholar": "semantic_scholar",
    "cr": "crossref",
}


def default_library() -> Path:
    configured = os.environ.get("TEZ_LIBRARY")
    if configured:
        return Path(configured)
    return Path.home() / "Documents" / "TEz Library"


@dataclass
class Settings:
    library: Path
    json: bool
    quiet: bool


def _sources(text: str | None) -> list[str]:
    if not text:
        return list(SOURCE_NAMES)
    names = [_SOURCE_ALIASES.get(n.strip().lower(), n.strip().lower()) for n in text.split(",")]
    unknown = [n for n in names if n not in SOURCE_NAMES]
    if unknown:
        raise CliFailure(ErrorCode.SOURCE_UNKNOWN.value, {"sources": ", ".join(unknown)})
    return list(dict.fromkeys(names))


def resolve_review(access: Access, wanted: str | None) -> ReviewView:
    """A review by id or title (Turkish-folded); the only one if none is named."""
    reviews = access.reviews()
    if wanted is None:
        if not reviews:
            raise CliFailure(ErrorCode.CLI_NO_REVIEW.value)
        if len(reviews) > 1:
            titles = ", ".join(f'"{r.title}"' for r in reviews)
            raise CliFailure(ErrorCode.CLI_REVIEW_REQUIRED.value, {"reviews": titles})
        return reviews[0]
    for review in reviews:
        if review.id == wanted or fold(review.title) == fold(wanted):
            return review
    raise CliFailure(ErrorCode.REVIEW_NOT_FOUND.value, {"review": wanted})


def build_app(m: Messages) -> typer.Typer:
    app = typer.Typer(
        name="tez",
        help=m("help.app"),
        add_completion=False,
        no_args_is_help=True,
        pretty_exceptions_enable=False,
        rich_markup_mode=None,
    )

    @app.callback()
    def common(  # pyright: ignore[reportUnusedFunction]
        ctx: typer.Context,
        library: Annotated[
            Path | None, typer.Option("--library", "-l", help=m("help.library"))
        ] = None,
        json_output: Annotated[bool, typer.Option("--json", help=m("help.json"))] = False,
        lang: Annotated[str | None, typer.Option("--lang", help=m("help.lang"))] = None,
        quiet: Annotated[bool, typer.Option("--quiet", "-q", help=m("help.quiet"))] = False,
    ) -> None:
        del lang  # read before the app was built, so --help is in that language too
        ctx.obj = Settings(library=library or default_library(), json=json_output, quiet=quiet)

    def run(ctx: typer.Context, work: Callable[[Access, Say], tuple[dict[str, Any], int]]) -> None:
        """Connect, do the work, report; exit with its code. Errors become exit 1."""
        settings: Settings = ctx.obj

        def say(text: str) -> None:
            if not settings.quiet and not settings.json:
                typer.echo(text)

        try:
            access = connect(settings.library)
        except CliFailure as failure:
            fail(settings, failure)
        try:
            if access.mode == "api":
                say(m("out.via_api"))
            else:
                say(m("out.direct", path=settings.library.absolute()))
            result, code = work(access, say)
        except CliFailure as failure:
            fail(settings, failure)
        except TezError as error:
            fail(settings, CliFailure.of(error))
        finally:
            access.close()
        if settings.json:
            typer.echo(to_json({"mode": access.mode, **result}))
        raise typer.Exit(code)

    def fail(settings: Settings, failure: CliFailure) -> NoReturn:
        if settings.json:
            typer.echo(to_json({"error": {"code": failure.code, "params": failure.params}}))
        else:
            typer.echo(f"tez: {m.error(failure.code, failure.params)}", err=True)
        raise typer.Exit(EXIT_FAILED)

    @app.command(help=m("help.search"))
    def search(
        ctx: typer.Context,
        query: Annotated[str, typer.Argument(help=m("help.search.query"))],
        sources: Annotated[
            str | None, typer.Option("--sources", "-s", help=m("help.search.sources"))
        ] = None,
        review: Annotated[str | None, typer.Option("--review", "-r", help=m("help.review"))] = None,
        year_from: Annotated[
            int | None, typer.Option("--year-from", help=m("help.search.year_from"))
        ] = None,
        year_to: Annotated[
            int | None, typer.Option("--year-to", help=m("help.search.year_to"))
        ] = None,
        limit: Annotated[
            int, typer.Option("--limit", min=1, max=5000, help=m("help.search.limit"))
        ] = 1000,
    ) -> None:
        def work(access: Access, say: Say) -> tuple[dict[str, Any], int]:
            names = _sources(sources)
            target = resolve_review(access, review)
            request = SearchRequest(query=query, year_from=year_from, year_to=year_to, limit=limit)

            def progress(update: SourceProgress) -> None:
                state = {
                    SourceState.SEARCHING: lambda: m("out.state.searching"),
                    SourceState.RATE_LIMITED: lambda: m(
                        "out.state.rate_limited", seconds=round(update.wait_seconds or 0)
                    ),
                    SourceState.DONE: lambda: m("out.state.done", retrieved=update.retrieved),
                    SourceState.PARTIAL: lambda: m("out.state.partial", retrieved=update.retrieved),
                    SourceState.FAILED: lambda: m(
                        "out.state.failed", error=m.error(update.error_code or "unknown", {})
                    ),
                }.get(update.state)
                if state is not None:
                    say(f"  {update.source}: {state()}")

            overview = access.search(target.id, request, names, progress)
            say(
                m(
                    "out.search_done",
                    retrieved=overview.retrieved,
                    duplicates=overview.duplicates,
                    unique=overview.unique,
                    search_id=overview.search_id,
                )
            )
            statuses = {run.status for run in overview.runs}
            code = EXIT_OK
            if statuses == {RunStatus.ERROR}:
                code = EXIT_FAILED
            elif statuses != {RunStatus.OK}:
                code = EXIT_PARTIAL
            return {"search": overview}, code

        run(ctx, work)

    @app.command(name="import", help=m("help.import"))
    def import_(
        ctx: typer.Context,
        file: Annotated[Path, typer.Argument(help=m("help.import.file"))],
        source: Annotated[str, typer.Option("--source", help=m("help.import.source"))],
        searched_at: Annotated[
            datetime | None,
            typer.Option("--searched-at", formats=["%Y-%m-%d"], help=m("help.import.searched_at")),
        ] = None,
        query: Annotated[str | None, typer.Option("--query", help=m("help.import.query"))] = None,
        review: Annotated[str | None, typer.Option("--review", "-r", help=m("help.review"))] = None,
        screening: Annotated[
            bool, typer.Option("--screening/--no-screening", help=m("help.import.screening"))
        ] = True,
        to_library: Annotated[
            bool, typer.Option("--library-too", help=m("help.import.library"))
        ] = False,
    ) -> None:
        def work(access: Access, say: Say) -> tuple[dict[str, Any], int]:
            target = resolve_review(access, review)
            day: date | None = searched_at.date() if searched_at else None
            request = ImportRequest(
                file_name=file.name,
                path=str(file.absolute()),
                review_id=target.id,
                log=ImportLog(source=source, searched_at=day, query=query),
                add_to_review=screening,
                add_to_library=to_library,
            )
            outcome = access.import_file(request)
            say(
                m(
                    "out.import_done",
                    total=outcome.total,
                    imported=outcome.imported,
                    new=outcome.new_papers,
                    to_review=outcome.added_to_review,
                )
            )
            for issue in outcome.issues:
                line = issue.line if issue.line is not None else "?"
                reason = m.error(issue.code.value, {})
                say(m("out.import_issue", line=line, key=issue.key or "", code=reason))
            return {"import": outcome}, EXIT_PARTIAL if outcome.issues else EXIT_OK

        run(ctx, work)

    @app.command(help=m("help.add"))
    def add(
        ctx: typer.Context,
        paths: Annotated[list[Path], typer.Argument(help=m("help.add.paths"))],
        collection: Annotated[
            str | None, typer.Option("--collection", "-c", help=m("help.add.collection"))
        ] = None,
    ) -> None:
        def work(access: Access, say: Say) -> tuple[dict[str, Any], int]:
            files: list[str] = []
            for path in paths:
                if path.is_dir():
                    files += [
                        str(p.absolute())
                        for p in sorted(path.rglob("*"))
                        if p.is_file() and p.suffix.lower() == ".pdf"
                    ]
                else:
                    files.append(str(path.absolute()))
            results = access.add_pdfs(files)
            for result in results:
                if result.added is not None:
                    word = m("out.added" if result.added.status == "added" else "out.duplicate")
                    say(f"  {Path(result.path).name}: {word}")
                elif result.error is not None:
                    say(f"  {Path(result.path).name}: {m.error(result.error.code, {})}")
            stored = [r.added.paper_id for r in results if r.added is not None]
            filed = None
            if collection and stored:
                existing = next(
                    (
                        c
                        for c in access.collections()
                        if not c.is_system and fold(c.name) == fold(collection)
                    ),
                    None,
                )
                target = existing or access.create_collection(collection)
                access.file_in(target.id, stored)
                filed = target
                say(m("out.filed", name=target.name))
            added = sum(1 for r in results if r.added and r.added.status == "added")
            duplicates = sum(1 for r in results if r.added and r.added.status == "duplicate")
            failed = len(results) - added - duplicates
            say(m("out.add_done", added=added, duplicates=duplicates, failed=failed))
            if access.mode == "direct" and added:
                say(m("out.add_later"))
            code = EXIT_OK
            if failed and (added or duplicates):
                code = EXIT_PARTIAL
            elif failed or not results:
                code = EXIT_FAILED
            return {"results": results, "collection": filed}, code

        run(ctx, work)

    @app.command(help=m("help.export"))
    def export(
        ctx: typer.Context,
        fmt: Annotated[
            str, typer.Option("--format", "-f", help=m("help.export.format"))
        ] = "bibtex",
        review: Annotated[
            str | None, typer.Option("--review", "-r", help=m("help.export.review"))
        ] = None,
        collection: Annotated[
            str | None, typer.Option("--collection", "-c", help=m("help.export.collection"))
        ] = None,
        output: Annotated[
            Path | None, typer.Option("--output", "-o", help=m("help.export.output"))
        ] = None,
    ) -> None:
        settings: Settings = ctx.obj

        def work(access: Access, say: Say) -> tuple[dict[str, Any], int]:
            if fmt not in ("bibtex", "ris"):
                raise CliFailure(ErrorCode.REQUEST_INVALID.value, {"format": fmt})
            review_id = resolve_review(access, review).id if review else None
            collection_id = None
            if collection:
                found = next(
                    (
                        c
                        for c in access.collections()
                        if fold(c.name) == fold(collection) or c.id == collection
                    ),
                    None,
                )
                if found is None:
                    raise CliFailure(ErrorCode.COLLECTION_NOT_FOUND.value, {"name": collection})
                collection_id = found.id
            result = access.export(fmt, review_id, collection_id)
            if output is None:
                if not settings.json:
                    typer.echo(result.content, nl=False)
                return {"export": result}, EXIT_OK
            output.write_text(result.content, encoding="utf-8", newline="\n")
            say(m("out.export_done", count=result.count, path=output.absolute()))
            summary = {"format": result.format, "count": result.count, "path": str(output)}
            return {"export": summary}, EXIT_OK

        run(ctx, work)

    return app


def _utf8_streams() -> None:
    """UTF-8 always: Windows would otherwise write pipes and files in the ANSI code page,
    and `tez --json | ...` would break on "ş" or "İ"."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def _quiet_logs() -> None:
    """The terminal shows the command's own report, not library warnings (a parser's note on
    a broken BibTeX entry is already reported as a skipped entry). TEZ_LOG_LEVEL brings the
    app's logs back, to stderr."""
    if os.environ.get("TEZ_LOG_LEVEL"):
        configure_logging(AppSettings())
    else:
        logging.getLogger().addHandler(logging.NullHandler())


def main(argv: list[str] | None = None) -> None:
    _utf8_streams()
    _quiet_logs()
    arguments = list(sys.argv[1:] if argv is None else argv)
    language = detect_language(arguments)
    translate_click(language)
    app = build_app(Messages(language))
    app(args=arguments, prog_name="tez")


if __name__ == "__main__":
    main()
