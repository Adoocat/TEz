"""Which degree a thesis is for, read from the free text sources give ("Master's thesis",
"Doktora Tezi", BibLaTeX's `mathesis`). Unknown stays unknown: a bare "dissertation" is a
doctoral thesis in some countries and a master's in others."""

import re

from tez.modules.library.models import ThesisType
from tez.shared.text import fold

# Folded text (tez.shared.text.fold): Turkish letters and case do not matter.
_DOCTORAL = re.compile(r"\bph\.?\s?d\b|phdthesis|doctor|doktora|\bd\.?phil\b|sanatta yeterlik")
_MASTERS = re.compile(r"master|\bm\.?\s?sc?\b|\bm\.?\s?a\b|mathesis|yuksek lisans|magister")


def thesis_type_from_text(text: str | None) -> ThesisType | None:
    folded = fold(text or "")
    if _DOCTORAL.search(folded):
        return ThesisType.DOCTORAL
    if _MASTERS.search(folded):
        return ThesisType.MASTERS
    return None
