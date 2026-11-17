"""Optional modules: manifest validation, fingerprints and the catalogue (unit).

Pure data checks: nothing is downloaded, and the catalogue is read from files that
the test writes into ``tmp_path``.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from trigger_designer.core.modules import (
    Catalogue,
    ModuleError,
    ModuleFile,
    ModuleManifest,
    load_catalogue,
    parse_manifest,
)
from trigger_designer.core.modules.catalogue import (
    ENV_CATALOGUE,
    bundled_catalogue_path,
)

pytestmark = pytest.mark.unit

SHA_A = "a" * 64
SHA_B = "b" * 64


def valid() -> dict:
    return {
        "id": "fuzzy-model",
        "name": "Fuzzy match model",
        "version": "1.0.0",
        "description": "A small local model that Fuzzy Match can use offline.",
        "license": "MIT",
        "homepage": "https://example.com/fuzzy-model",
        "files": [
            {
                "name": "model.bin",
                "url": "https://files.example.com/model.bin",
                "size_bytes": 1000,
                "sha256": SHA_A,
            },
            {
                "name": "vocab.txt",
                "url": "https://files.example.com/vocab.txt",
                "size_bytes": 200,
                "sha256": SHA_B,
            },
        ],
    }


def invalid(mutate) -> dict:
    data = copy.deepcopy(valid())
    mutate(data)
    return data


def _set(path: tuple, value):
    """A mutator that sets the value found at ``path`` (keys and list indexes)."""

    def mutate(data):
        target = data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


def _drop(path: tuple):
    """A mutator that removes the key found at ``path``."""

    def mutate(data):
        target = data
        for key in path[:-1]:
            target = target[key]
        del target[path[-1]]

    return mutate


def _files(count: int, size: int) -> list[dict]:
    return [
        {
            "name": f"part{index}.bin",
            "url": "https://files.example.com/part.bin",
            "size_bytes": size,
            "sha256": SHA_A,
        }
        for index in range(count)
    ]


INVALID = [
    pytest.param(_set(("id",), "Fuzzy-Model"), "id", id="id-uppercase"),
    pytest.param(_set(("id",), "ab"), "id", id="id-too-short"),
    pytest.param(_set(("id",), "1model"), "id", id="id-starts-with-digit"),
    pytest.param(_set(("id",), "x" * 41), "id", id="id-too-long"),
    pytest.param(_set(("id",), "con"), "id", id="id-windows-device-name"),
    pytest.param(
        _set(("files", 0, "url"), "http://files.example.com/model.bin"),
        "files[0].url",
        id="url-not-https",
    ),
    pytest.param(
        _set(("files", 0, "url"), "https://user:pw@files.example.com/model.bin"),
        "files[0].url",
        id="url-with-credentials",
    ),
    pytest.param(
        _set(("files", 0, "url"), "https:///model.bin"),
        "files[0].url",
        id="url-without-host",
    ),
    pytest.param(
        _set(("files", 0, "name"), "../evil.bin"), "files[0].name", id="name-traversal"
    ),
    pytest.param(
        _set(("files", 0, "name"), "sub/model.bin"), "files[0].name", id="name-folder"
    ),
    pytest.param(
        _set(("files", 0, "name"), ".hidden"), "files[0].name", id="name-leading-dot"
    ),
    pytest.param(
        _set(("files", 0, "name"), "module.json"), "files[0].name", id="name-reserved"
    ),
    pytest.param(
        _set(("files", 0, "name"), "CON.bin"), "files[0].name", id="name-device"
    ),
    pytest.param(
        _set(("files", 1, "name"), "MODEL.bin"),
        "files[1].name",
        id="name-repeats-ignoring-case",
    ),
    pytest.param(
        _set(("files", 0, "sha256"), "ABC"), "files[0].sha256", id="sha-short"
    ),
    pytest.param(
        _set(("files", 0, "sha256"), "A" * 64), "files[0].sha256", id="sha-uppercase"
    ),
    pytest.param(
        _set(("files", 0, "size_bytes"), 0), "files[0].size_bytes", id="size-zero"
    ),
    pytest.param(
        _set(("files", 0, "size_bytes"), True), "files[0].size_bytes", id="size-bool"
    ),
    pytest.param(
        _set(("files", 0, "size_bytes"), 2_147_483_649),
        "files[0].size_bytes",
        id="size-over-limit",
    ),
    pytest.param(_set(("files",), []), "files", id="no-files"),
    pytest.param(_set(("files",), _files(21, 10)), "files", id="too-many-files"),
    pytest.param(
        _set(("files",), _files(3, 2_147_483_648)), "files", id="total-over-limit"
    ),
    pytest.param(_set(("files", 0), "not-an-object"), "files[0]", id="file-not-object"),
    pytest.param(_drop(("license",)), "license", id="missing-license"),
    pytest.param(_set(("extra",), 1), "extra", id="unknown-field"),
    pytest.param(_set(("name",), 5), "name", id="name-not-text"),
    pytest.param(_set(("name",), "n" * 81), "name", id="name-too-long"),
    pytest.param(_set(("version",), ""), "version", id="version-empty"),
    pytest.param(_set(("version",), "1" * 33), "version", id="version-too-long"),
    pytest.param(
        _set(("description",), "d" * 501), "description", id="description-too-long"
    ),
    pytest.param(
        _set(("license",), "bad\x07license"), "license", id="control-character"
    ),
    pytest.param(
        _set(("homepage",), "http://example.com"), "homepage", id="homepage-not-https"
    ),
]


@pytest.mark.parametrize(("mutate", "field"), INVALID)
def test_every_invalid_field_is_rejected_by_name(mutate, field):
    with pytest.raises(ModuleError) as caught:
        parse_manifest(invalid(mutate))
    assert caught.value.code == "TD-MOD-001"
    assert field in caught.value.message


def test_a_manifest_that_is_not_an_object_is_rejected():
    with pytest.raises(ModuleError) as caught:
        parse_manifest(["not", "a", "module"])
    assert caught.value.code == "TD-MOD-001"


def test_a_valid_manifest_parses_to_typed_fields():
    manifest = parse_manifest(valid())
    assert isinstance(manifest, ModuleManifest)
    assert manifest.id == "fuzzy-model"
    assert manifest.version == "1.0.0"
    assert manifest.homepage == "https://example.com/fuzzy-model"
    assert manifest.files[0] == ModuleFile(
        name="model.bin",
        url="https://files.example.com/model.bin",
        size_bytes=1000,
        sha256=SHA_A,
    )


def test_homepage_is_optional():
    data = valid()
    del data["homepage"]
    assert parse_manifest(data).homepage == ""


def test_to_dict_round_trips_through_parse_manifest():
    manifest = parse_manifest(valid())
    assert parse_manifest(manifest.to_dict()) == manifest


def test_fingerprint_is_the_sha256_of_the_canonical_json():
    manifest = parse_manifest(valid())
    canonical = json.dumps(manifest.to_dict(), sort_keys=True, separators=(",", ":"))
    assert (
        manifest.fingerprint() == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    )


def test_fingerprint_is_stable_for_equal_manifests():
    assert (
        parse_manifest(valid()).fingerprint() == parse_manifest(valid()).fingerprint()
    )


@pytest.mark.parametrize(
    "mutate",
    [
        _set(("name",), "Another name"),
        _set(("version",), "1.0.1"),
        _set(("description",), "A different description."),
        _set(("license",), "Apache-2.0"),
        _set(("homepage",), "https://example.com/other"),
        _set(("files", 0, "url"), "https://files.example.com/other.bin"),
        _set(("files", 0, "size_bytes"), 1001),
        _set(("files", 0, "sha256"), SHA_B),
        _set(("files", 0, "name"), "other.bin"),
    ],
)
def test_fingerprint_changes_when_any_field_changes(mutate):
    base = parse_manifest(valid()).fingerprint()
    assert parse_manifest(invalid(mutate)).fingerprint() != base


def test_hosts_are_sorted_unique_names_and_total_size_adds_up():
    manifest = parse_manifest(valid())
    assert manifest.hosts == ("files.example.com",)
    assert manifest.total_size == 1200
    data = valid()
    data["files"][1]["url"] = "https://cdn.example.org/vocab.txt"
    other = parse_manifest(data)
    assert other.hosts == ("cdn.example.org", "files.example.com")


# ------------------------------------------------------------------ catalogue
def _catalogue_file(tmp_path: Path, entries: list, schema: int = 1) -> Path:
    path = tmp_path / "catalogue.json"
    path.write_text(
        json.dumps({"schema": schema, "modules": entries}), encoding="utf-8"
    )
    return path


def test_the_bundled_catalogue_loads_empty(monkeypatch):
    monkeypatch.delenv(ENV_CATALOGUE, raising=False)
    catalogue = load_catalogue()
    assert isinstance(catalogue, Catalogue)
    assert catalogue.modules == ()
    assert catalogue.problems == ()
    assert catalogue.source == "bundled"
    bundled = json.loads(bundled_catalogue_path().read_text(encoding="utf-8"))
    assert bundled == {"schema": 1, "modules": []}


def test_a_catalogue_file_given_as_an_argument_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_CATALOGUE, raising=False)
    path = _catalogue_file(tmp_path, [valid()])
    catalogue = load_catalogue(path)
    assert [item.id for item in catalogue.modules] == ["fuzzy-model"]
    assert catalogue.problems == ()
    assert catalogue.source == str(path)


def test_a_catalogue_file_named_by_the_environment_is_read(tmp_path, monkeypatch):
    path = _catalogue_file(tmp_path, [valid()])
    monkeypatch.setenv(ENV_CATALOGUE, str(path))
    catalogue = load_catalogue()
    assert [item.id for item in catalogue.modules] == ["fuzzy-model"]
    assert catalogue.source == str(path)


def test_a_bad_entry_is_skipped_and_reported(tmp_path):
    broken = valid()
    broken["id"] = "Broken Id"
    other = valid()
    other["id"] = "other-model"
    path = _catalogue_file(tmp_path, [valid(), broken, other])
    catalogue = load_catalogue(path)
    assert [item.id for item in catalogue.modules] == ["fuzzy-model", "other-model"]
    assert len(catalogue.problems) == 1
    assert "Entry 2" in catalogue.problems[0]
    assert "'id'" in catalogue.problems[0]


def test_a_duplicate_id_keeps_the_first_entry(tmp_path):
    first = valid()
    first["name"] = "First"
    second = valid()
    second["name"] = "Second"
    catalogue = load_catalogue(_catalogue_file(tmp_path, [first, second]))
    assert [item.name for item in catalogue.modules] == ["First"]
    assert len(catalogue.problems) == 1
    assert "already listed" in catalogue.problems[0]


def test_a_missing_file_gives_an_empty_catalogue_with_a_problem(tmp_path):
    catalogue = load_catalogue(tmp_path / "missing.json")
    assert catalogue.modules == ()
    assert len(catalogue.problems) == 1
    assert "not found" in catalogue.problems[0]


def test_a_file_that_is_not_json_is_empty_with_a_problem(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    catalogue = load_catalogue(broken)
    assert catalogue.modules == ()
    assert "not valid JSON" in catalogue.problems[0]


def test_an_unknown_schema_is_empty_with_a_problem(tmp_path):
    catalogue = load_catalogue(_catalogue_file(tmp_path, [valid()], schema=2))
    assert catalogue.modules == ()
    assert "schema" in catalogue.problems[0]
