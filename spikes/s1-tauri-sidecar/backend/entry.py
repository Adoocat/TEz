"""PyInstaller entry point (PyInstaller needs a script, not a package)."""

import sys

from tez_backend.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
