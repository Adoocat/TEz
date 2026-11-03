"""Process configuration from `TEZ_*` environment variables.

Secrets never live here: the API token is passed to `create_app` directly and API keys
go to the OS keyring.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
LogFormat = Literal["json", "console"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEZ_", extra="ignore", frozen=True)

    log_level: LogLevel = "INFO"
    log_format: LogFormat = "json"
    # Browser origins allowed to call the API: the Tauri webview (Windows) and the Vite dev server.
    cors_origins: list[str] = ["http://tauri.localhost", "http://localhost:1420"]
    # How long a worker may hold a job without a heartbeat before another may take it over.
    job_lease_seconds: float = 30.0
    # How often an idle worker looks for new jobs.
    worker_poll_seconds: float = 0.5

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value
