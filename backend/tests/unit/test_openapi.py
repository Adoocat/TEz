import json
import subprocess
import sys

from tez.openapi import build_schema, render


def test_schema_lists_the_api() -> None:
    paths = build_schema()["paths"]

    assert {"/health", "/library", "/jobs", "/jobs/{job_id}", "/jobs/events"} <= set(paths)


def test_output_is_stable_and_free_of_secrets() -> None:
    first, second = render(build_schema()), render(build_schema())

    assert first == second
    assert "schema-only" not in first


def test_module_prints_utf8_json_with_lf() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tez.openapi"], capture_output=True, check=True, timeout=60
    )

    assert b"\r\n" not in result.stdout
    assert json.loads(result.stdout.decode("utf-8"))["info"]["title"] == "TEz"
