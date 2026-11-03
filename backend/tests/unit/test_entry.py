from pathlib import Path
from typing import Any

import pytest

from tez import __main__ as entry

Call = tuple[tuple[Any, ...], dict[str, Any]]


@pytest.fixture
def uvicorn_calls(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    calls: list[Call] = []
    monkeypatch.setattr(entry.uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    return calls


def test_serve_starts_uvicorn_with_factory(uvicorn_calls: list[Call]) -> None:
    entry.main(["serve", "--port", "9999"])

    assert uvicorn_calls == [
        (
            ("tez.main:create_app",),
            {
                "factory": True,
                "host": "127.0.0.1",
                "port": 9999,
                "reload": False,
                "reload_dirs": None,
            },
        )
    ]


def test_reload_watches_only_the_package(uvicorn_calls: list[Call]) -> None:
    entry.main(["serve", "--reload"])

    ((_, kwargs),) = uvicorn_calls
    assert kwargs["reload"] is True
    assert kwargs["reload_dirs"] == [str(Path(entry.__file__).parent)]


def test_mode_is_required() -> None:
    with pytest.raises(SystemExit) as exc:
        entry.main([])

    assert exc.value.code == 2
