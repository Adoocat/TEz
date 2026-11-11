"""Where PDFs live in the library folder: `files/<first 2 hex>/<sha256>.pdf` (plan, folder layout).

The name is the content's hash, so the same file is stored once and a stored file never changes.
"""

import hashlib
import os
from pathlib import Path

from tez.shared.ids import new_id

FILES_FOLDER = "files"
_PDF_MAGIC = b"%PDF-"
# The header may follow some junk; readers accept it within the first kilobyte.
_MAGIC_WINDOW = 1024


def looks_like_pdf(data: bytes) -> bool:
    return _PDF_MAGIC in data[:_MAGIC_WINDOW]


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_path(sha256: str) -> str:
    return f"{FILES_FOLDER}/{sha256[:2]}/{sha256}.pdf"


def store(library_path: Path, data: bytes, sha256: str) -> str:
    """Write the file under its hash, atomically; returns the path relative to the library.

    A file already there (from an earlier attempt that did not reach the database) is kept:
    its name says its content is the same.
    """
    relative = relative_path(sha256)
    target = library_path / relative
    if target.is_file():
        return relative
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(f".{new_id()}.part")
    try:
        with partial.open("wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return relative
