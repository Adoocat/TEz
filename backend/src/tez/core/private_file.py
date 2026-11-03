"""Writing files that only the current user may read (they hold secrets such as API tokens).

The permissions are set on an empty temporary file before the content is written, then the
file is moved into place, so the secret is never readable by others, not even briefly.
"""

import getpass
import os
import subprocess
import sys
from pathlib import Path


def write_private_text(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    if sys.platform == "win32":
        tmp.touch()
        _restrict_to_current_user(tmp)
    else:
        os.close(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as file:
            file.write(content)
        # A move within the folder keeps the file's own permissions on Windows and Unix.
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _restrict_to_current_user(path: Path) -> None:
    """Drop inherited permissions and grant full control to the current user only."""
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
        check=True,
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
