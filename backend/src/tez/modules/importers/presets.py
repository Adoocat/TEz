"""Database presets for importing exports (Task 26): the user picks the database, and TEz
knows its name for the search record and the quirks of its export.

A preset is offered only once a real, small export from that database is in the test data
(`tests/fixtures/imports/presets/<key>/`) and its test passes; until then it stays hidden and
the file can still be imported as plain RIS or BibTeX. Samples are never invented.
"""

from dataclasses import dataclass

from tez.core.errors import ErrorCode, TezError
from tez.modules.importers.parsing import ImportFormat


@dataclass(frozen=True)
class DatabasePreset:
    key: str
    # As the import's `search_run.source`, so PRISMA names the database.
    name: str
    # The formats of its exports TEz reads, best first.
    formats: tuple[ImportFormat, ...]


_RIS_BIB = (ImportFormat.RIS, ImportFormat.BIBTEX)

PRESETS: tuple[DatabasePreset, ...] = (
    # Web of Science plain text and Scopus CSV need their own readers; they come with a
    # sample. Until then their RIS and BibTeX exports are the way in.
    DatabasePreset("wos", "Web of Science", _RIS_BIB),
    DatabasePreset("scopus", "Scopus", _RIS_BIB),
    DatabasePreset("jstor", "JSTOR", (ImportFormat.RIS,)),
    DatabasePreset("ebsco", "EBSCO", (ImportFormat.RIS,)),
    DatabasePreset("proquest", "ProQuest", (ImportFormat.RIS,)),
    DatabasePreset("psycinfo", "APA PsycInfo", (ImportFormat.RIS,)),
    DatabasePreset("ieee", "IEEE Xplore", _RIS_BIB),
    DatabasePreset("acm", "ACM DL", (ImportFormat.BIBTEX, ImportFormat.RIS)),
    DatabasePreset("scholar", "Google Scholar", (ImportFormat.BIBTEX,)),
    DatabasePreset("trdizin", "TR Dizin", (ImportFormat.BIBTEX,)),
    DatabasePreset("yoktez", "YÖK Tez", (ImportFormat.RIS, ImportFormat.BIBTEX)),
)

# Keys whose real sample export is in the test data and tested. Add a key only with its sample.
VERIFIED: frozenset[str] = frozenset()


def available() -> list[DatabasePreset]:
    """The presets the user is offered: those verified with a real export."""
    return [preset for preset in PRESETS if preset.key in VERIFIED]


def get_available(key: str) -> DatabasePreset:
    preset = next((p for p in available() if p.key == key), None)
    if preset is None:
        raise TezError(ErrorCode.IMPORT_PRESET_UNAVAILABLE, {"preset": key}, status=422)
    return preset
