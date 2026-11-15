"""Providers are tested against recorded real responses; these tests never reach the network."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from tez.shared.http import HttpClient


async def no_sleep(_: float) -> None:
    """Replays need no politeness: the limiter and back-off would only slow the tests."""


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    return {
        # Whatever a recording ran with, keys and e-mail addresses stay out of the repo.
        "filter_headers": ["authorization", "x-api-key", "user-agent", "cookie", "set-cookie"],
        "filter_query_parameters": ["api_key", "mailto", "email"],
        "decode_compressed_response": True,
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    source = request.module.__name__.rsplit(".", 1)[-1].removeprefix("test_")
    return str(Path(__file__).parents[2] / "cassettes" / source)


def run_with_http[T](use: Callable[[HttpClient], Awaitable[T]]) -> T:
    """Run `use` with a real client whose waits return at once."""

    async def main() -> T:
        async with HttpClient(sleep=no_sleep) as http:
            return await use(http)

    return asyncio.run(main())
