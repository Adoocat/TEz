"""The links in a note's Markdown.

Two ways to write one: `[Kim et al. 2024, p. 7](tez:anchor/<id>)`, which the editor inserts and
which survives renaming, and `[[A title or citation key]]`, for typing by hand. Links inside code
are text.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass

from tez.modules.notes.models import LinkTarget

_CODE = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*`", re.DOTALL)
_LINK = re.compile(
    r"\[(?P<label>[^\[\]\n]*)\]\(tez:(?P<type>note|paper|anchor)/(?P<id>[0-9A-Za-z-]{1,36})\)"
    r"|\[\[(?P<name>[^\[\]\n]+)\]\]"
)


@dataclass(frozen=True)
class WrittenLink:
    label: str
    # Both None for `[[name]]`, where the label is the name to look up.
    target_type: LinkTarget | None
    target_id: str | None


def links_in(body: str) -> Iterator[WrittenLink]:
    readable = _CODE.sub(lambda found: " " * len(found[0]), body)
    for found in _LINK.finditer(readable):
        if found["name"] is not None:
            yield WrittenLink(found["name"].strip(), None, None)
        else:
            yield WrittenLink(found["label"], LinkTarget(found["type"]), found["id"])


def plain_text(body: str) -> str:
    """The note as it reads: links by their words, without addresses."""
    return _LINK.sub(lambda found: found["name"] or found["label"] or "", body)


def retarget(body: str, name: str, label: str, target: LinkTarget, target_id: str) -> str:
    """`[[name]]` written as a link to a known target (a renamed note keeps its links)."""
    safe = label.replace("[", "(").replace("]", ")")
    pattern = re.compile(r"\[\[\s*" + re.escape(name) + r"\s*\]\]")
    return pattern.sub(lambda _: f"[{safe}](tez:{target.value}/{target_id})", body)
