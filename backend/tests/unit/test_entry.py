import os
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tez import __main__ as entry
from tez.main import DEV_LIBRARY_ENV, DEV_TOKEN_ENV, DEV_URL_ENV, create_dev_app
from tez.modules.library.schemas import Instance
from tez.modules.library.service import find_instance, open_library

Call = tuple[tuple[Any, ...], dict[str, Any]]


@pytest.fixture
def uvicorn_calls(monkeypatch: pytest.MonkeyPatch) -> list[Call]:
    calls: list[Call] = []
    monkeypatch.setattr(entry.uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    # main() configures logging and may export variables; keep both local to the test.
    monkeypatch.setattr(entry, "configure_logging", lambda *a, **kw: None)
    for name in (DEV_TOKEN_ENV, DEV_LIBRARY_ENV, DEV_URL_ENV, "TEZ_LOG_FORMAT"):
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    return calls


def test_serve_runs_a_token_protected_app(
    uvicorn_calls: list[Call], capsys: pytest.CaptureFixture[str]
) -> None:
    entry.main(["serve", "--port", "9999"])

    ((args, kwargs),) = uvicorn_calls
    (app,) = args
    assert isinstance(app, FastAPI)
    assert kwargs == {"host": "127.0.0.1", "port": 9999, "log_config": None, "access_log": False}
    # The generated token is printed once, Jupyter-style, so the user can call the API.
    out = capsys.readouterr().out
    assert "http://127.0.0.1:9999" in out
    token = out.split("token: ")[1].split()[0]
    assert len(token) >= 32
    assert TestClient(app).get("/health").status_code == 401
    auth = {"Authorization": f"Bearer {token}"}
    assert TestClient(app).get("/health", headers=auth).status_code == 200


def test_each_start_gets_a_new_token(
    uvicorn_calls: list[Call], capsys: pytest.CaptureFixture[str]
) -> None:
    entry.main(["serve"])
    entry.main(["serve"])

    first, second = [part.split()[0] for part in capsys.readouterr().out.split("token: ")[1:]]
    assert first != second


def test_reload_uses_the_dev_factory_and_watches_only_the_package(
    uvicorn_calls: list[Call], monkeypatch: pytest.MonkeyPatch
) -> None:
    entry.main(["serve", "--reload"])

    ((args, kwargs),) = uvicorn_calls
    assert args == ("tez.main:create_dev_app",)
    assert kwargs["factory"] is True
    assert kwargs["reload"] is True
    assert kwargs["reload_dirs"] == [str(Path(entry.__file__).parent)]
    assert kwargs["log_config"] is None
    # The reloaded child process finds the token and console logging in its environment.
    assert len(os.environ[DEV_TOKEN_ENV]) >= 32
    assert os.environ["TEZ_LOG_FORMAT"] == "console"
    assert os.environ[DEV_URL_ENV] == "http://127.0.0.1:8787"


def test_reload_defaults_to_the_dev_library(uvicorn_calls: list[Call]) -> None:
    entry.main(["serve", "--reload"])

    backend = Path(entry.__file__).parents[2]
    assert os.environ[DEV_LIBRARY_ENV] == str(backend / ".dev" / "TEz Library")


def test_reload_with_an_explicit_library(uvicorn_calls: list[Call], tmp_path: Path) -> None:
    entry.main(["serve", "--reload", "--library", str(tmp_path / "Mine")])

    assert os.environ[DEV_LIBRARY_ENV] == str(tmp_path / "Mine")


def test_dev_factory_opens_and_publishes_the_dev_library(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    library = tmp_path / "Dev Library"
    monkeypatch.setenv(DEV_TOKEN_ENV, "dev-token-abc")
    monkeypatch.setenv(DEV_LIBRARY_ENV, str(library))
    monkeypatch.setenv(DEV_URL_ENV, "http://127.0.0.1:8787")
    monkeypatch.setattr("tez.main.configure_logging", lambda *a, **kw: None)

    with TestClient(create_dev_app()) as client:
        response = client.get("/library", headers={"Authorization": "Bearer dev-token-abc"})
        instance = find_instance(library)

    assert response.status_code == 200
    assert instance is not None
    assert instance.api is not None
    assert instance.api.url == "http://127.0.0.1:8787"
    assert find_instance(library) is None  # closed on shutdown


def test_serve_with_a_library_publishes_and_then_closes_it(
    uvicorn_calls: list[Call], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    library = tmp_path / "TEz Library"
    seen: list[Instance | None] = []
    # While "serving", the discovery file points at the API.
    monkeypatch.setattr(entry.uvicorn, "run", lambda *a, **kw: seen.append(find_instance(library)))

    entry.main(["serve", "--port", "9999", "--library", str(library), "--create"])

    (instance,) = seen
    assert instance is not None
    assert instance.api is not None
    assert instance.api.url == "http://127.0.0.1:9999"
    assert find_instance(library) is None


def test_serve_on_a_locked_library_exits_with_a_clear_message(
    uvicorn_calls: list[Call], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    library = tmp_path / "TEz Library"
    holder = open_library(library, create=True)
    try:
        with pytest.raises(SystemExit) as exc:
            entry.main(["serve", "--library", str(library)])
    finally:
        holder.close()

    assert exc.value.code == 3
    assert uvicorn_calls == []
    err = capsys.readouterr().err
    assert "library.locked" in err
    assert f"pid {os.getpid()}" in err
    assert str(library) in err


def test_dev_factory_opens_docs_and_uses_the_exported_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DEV_TOKEN_ENV, "dev-token-abc")
    monkeypatch.setattr("tez.main.configure_logging", lambda *a, **kw: None)

    client = TestClient(create_dev_app())

    assert client.get("/docs").status_code == 200
    assert client.get("/health").status_code == 401
    ok = client.get("/health", headers={"Authorization": "Bearer dev-token-abc"})
    assert ok.status_code == 200


def test_dev_factory_refuses_to_start_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DEV_TOKEN_ENV, "")
    monkeypatch.setattr("tez.main.configure_logging", lambda *a, **kw: None)

    with pytest.raises(ValueError, match="token"):
        create_dev_app()


def test_token_stdin_cannot_be_combined_with_reload(uvicorn_calls: list[Call]) -> None:
    with pytest.raises(SystemExit) as exc:
        entry.main(["serve", "--token-stdin", "--reload"])

    assert exc.value.code == 2
    assert uvicorn_calls == []


def test_mode_is_required() -> None:
    with pytest.raises(SystemExit) as exc:
        entry.main([])

    assert exc.value.code == 2
