"""Exclusive, non-blocking lock on a file, held by the OS for the life of the process.

The OS drops the lock when the process exits, even after a crash or a forced kill, so
there are no stale locks to clean up. Windows uses `msvcrt.locking` on the first byte,
Unix `flock`. Both conflict with a second handle opened by the same process too.
"""

import sys
from pathlib import Path
from typing import BinaryIO


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: BinaryIO | None = None

    @property
    def held(self) -> bool:
        return self._file is not None

    def try_acquire(self) -> bool:
        """Take the lock if nobody holds it. Never waits."""
        if self._file is not None:
            return True
        file = self.path.open("a+b")
        try:
            _lock(file)
        except OSError:
            file.close()
            return False
        self._file = file
        return True

    def release(self) -> None:
        if self._file is None:
            return
        try:
            _unlock(self._file)
        finally:
            self._file.close()
            self._file = None


def is_locked(path: Path) -> bool:
    """Whether another handle holds the lock at `path` right now."""
    if not path.exists():
        return False
    probe = FileLock(path)
    if probe.try_acquire():
        probe.release()
        return False
    return True


if sys.platform == "win32":
    import msvcrt

    def _lock(file: BinaryIO) -> None:
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(file: BinaryIO) -> None:
        file.seek(0)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock(file: BinaryIO) -> None:
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(file: BinaryIO) -> None:
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
