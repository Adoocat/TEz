"""Print the API's OpenAPI schema as JSON (`python -m tez.openapi`).

`pnpm gen:api` turns it into the frontend's typed client; CI fails when the committed
client is out of date (Task 7). Built from the app factory, so no server or library is
needed and the output is the same on every machine.
"""

import json
import sys
from typing import Any

from tez.core.config import Settings
from tez.main import create_app


def build_schema() -> dict[str, Any]:
    # The token only guards requests; it does not appear in the schema.
    return create_app(token="schema-only", settings=Settings()).openapi()


def render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[union-attr]
    sys.stdout.write(render(build_schema()))


if __name__ == "__main__":
    main()
