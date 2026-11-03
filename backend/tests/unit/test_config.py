import pytest
from pydantic import ValidationError

from tez.core.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("TEZ_LOG_LEVEL", "TEZ_LOG_FORMAT", "TEZ_CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.log_format == "json"
    assert settings.cors_origins == ["http://tauri.localhost", "http://localhost:1420"]


def test_reads_tez_prefixed_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEZ_LOG_LEVEL", "debug")
    monkeypatch.setenv("TEZ_LOG_FORMAT", "console")
    monkeypatch.setenv("TEZ_CORS_ORIGINS", '["http://localhost:5000"]')

    settings = Settings()

    assert settings.log_level == "DEBUG"
    assert settings.log_format == "console"
    assert settings.cors_origins == ["http://localhost:5000"]


def test_rejects_unknown_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEZ_LOG_FORMAT", "xml")

    with pytest.raises(ValidationError):
        Settings()


def test_ignores_dotenv_files() -> None:
    # Configuration comes from the environment only; a stray .env must not change behavior.
    assert Settings.model_config.get("env_file") is None
