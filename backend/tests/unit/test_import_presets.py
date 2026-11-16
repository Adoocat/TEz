"""Task 26: database presets. A preset is offered only with a real sample export, tested here;
the others stay hidden and their files still import as plain RIS or BibTeX."""

import base64
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import AUTH, TOKEN
from tez.core.config import Settings
from tez.main import create_app
from tez.modules.importers import presets
from tez.modules.importers.parsing import ImportFormat
from tez.modules.importers.service import detect_format, parse_file
from tez.modules.library.models import IdentifierScheme
from tez.modules.library.service import Library, open_library
from tez.modules.search.schemas import NormalizedRecord

SAMPLES = Path(__file__).parents[1] / "fixtures" / "imports" / "presets"


def test_keys_and_names_are_unique() -> None:
    assert len({p.key for p in presets.PRESETS}) == len(presets.PRESETS)
    assert len({p.name for p in presets.PRESETS}) == len(presets.PRESETS)


def test_only_presets_with_a_sample_are_verified() -> None:
    with_samples = (
        {d.name for d in SAMPLES.iterdir() if any(d.iterdir())} if SAMPLES.exists() else set()
    )
    assert {p.key for p in presets.PRESETS} >= presets.VERIFIED
    # A verified preset without its real sample would be offered on faith.
    assert with_samples >= presets.VERIFIED


@pytest.mark.parametrize("key", sorted(presets.VERIFIED))
def test_every_sample_of_a_verified_preset_reads_cleanly(key: str) -> None:
    preset = next(p for p in presets.PRESETS if p.key == key)
    for sample in sorted((SAMPLES / key).iterdir()):
        parsed, text = parse_file(sample.name, sample.read_bytes())
        assert detect_format(sample.name, text) in preset.formats, sample.name
        assert parsed.records, sample.name
        assert not parsed.issues, (sample.name, parsed.issues)


def _records(key: str, name: str) -> list[NormalizedRecord]:
    parsed, _ = parse_file(name, (SAMPLES / key / name).read_bytes())
    return parsed.records


def test_google_scholar_bibtex_keeps_turkish_names_and_arxiv_ids() -> None:
    # Copied record by record from "Cite" → BibTeX, as Scholar has no bulk export.
    records = _records("scholar", "scholar.bib")

    assert len(records) == 5
    evaluating = next(r for r in records if r.title.startswith("Evaluating"))
    assert [a.display_name for a in evaluating.authors] == [
        "Umut Cihan",
        "Arda İçöz",
        "Vahid Haratian",
        "Eray Tüzün",
    ]
    assert evaluating.venue_type == "preprint"
    assert evaluating.identifiers == {IdentifierScheme.ARXIV: "2505.20206"}


def test_tr_dizin_ris_and_bibtex_hold_the_same_records() -> None:
    # The same six records, exported one by one with the site's own Ris and Bibtex buttons.
    ris = _records("trdizin", "trdizin.ris")
    bib = _records("trdizin", "trdizin.bib")

    assert len(ris) == len(bib) == 6
    assert [r.title for r in ris] == [r.title for r in bib]
    assert [r.year for r in ris] == [r.year for r in bib]


def test_tr_dizin_ris_is_the_better_export() -> None:
    # TR Dizin's BibTeX has keys with spaces, no abstracts and a name missing its Turkish
    # letter ("Seda Eygu"); its RIS has all of them, so the preset lists RIS first.
    ris = _records("trdizin", "trdizin.ris")
    bib = _records("trdizin", "trdizin.bib")
    preset = next(p for p in presets.PRESETS if p.key == "trdizin")

    assert all(r.abstract for r in ris)
    assert not any(r.abstract for r in bib)
    assert ris[0].authors[0].display_name == "Seda EYGÜ"
    assert bib[0].authors[0].display_name == "Seda Eygu"
    assert preset.formats[0] is ImportFormat.RIS


def test_yok_tez_has_no_preset() -> None:
    # Checked 2026-11-16: the site exports no file, only formatted citations to the
    # clipboard, so it is not a file-road source (ADR 0019).
    assert "yoktez" not in {p.key for p in presets.PRESETS}


@pytest.fixture
def library(tmp_path: Path) -> Iterator[Library]:
    opened = open_library(tmp_path / "lib", create=True)
    yield opened
    opened.close()


@pytest.fixture
def client(library: Library) -> Iterator[TestClient]:
    app = create_app(token=TOKEN, settings=Settings(), library=library)
    with TestClient(app, headers=AUTH, raise_server_exceptions=False) as c:
        yield c


RIS = "TY  - JOUR\nTI  - Öğretmen adaylarında kaygı\nPY  - 2024\nER  - \n"


def _import(client: TestClient, review_id: str, log: dict[str, object]) -> dict[str, object]:
    response = client.post(
        "/imports",
        json={
            "file_name": "export.ris",
            "content_base64": base64.b64encode(RIS.encode()).decode(),
            "review_id": review_id,
            "log": log,
        },
    )
    return {"status": response.status_code, **response.json()}


def test_hidden_presets_are_not_offered_or_accepted(client: TestClient) -> None:
    review_id = client.post("/reviews", json={"title": "SLR"}).json()["id"]
    hidden = [p.key for p in presets.PRESETS if p.key not in presets.VERIFIED]

    offered = {p["key"] for p in client.get("/imports/presets").json()}
    refused = _import(client, review_id, {"preset": hidden[0]})

    assert offered.isdisjoint(hidden)
    assert refused["status"] == 422
    assert refused["error"] == {
        "code": "import.preset_unavailable",
        "params": {"preset": hidden[0]},
    }


def test_a_verified_preset_names_the_source(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(presets, "VERIFIED", frozenset({"jstor"}))
    review_id = client.post("/reviews", json={"title": "SLR"}).json()["id"]

    offered = client.get("/imports/presets").json()
    imported = _import(client, review_id, {"preset": "jstor"})

    assert offered == [{"key": "jstor", "name": "JSTOR", "formats": ["ris"]}]
    assert imported["status"] == 201
    (search,) = client.get("/searches", params={"review_id": review_id}).json()
    assert [run["source"] for run in search["runs"]] == ["JSTOR"]


@pytest.mark.parametrize(
    "log",
    [{"preset": "jstor", "source": "JSTOR"}, {"preset": "jstor", "saved_search_id": "x"}],
)
def test_a_preset_is_the_source(client: TestClient, log: dict[str, object]) -> None:
    review_id = client.post("/reviews", json={"title": "SLR"}).json()["id"]
    assert _import(client, review_id, log)["status"] == 422
