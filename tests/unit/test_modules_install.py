"""Optional modules: installing, with the network replaced by a fake (unit).

``opener`` serves bytes from memory, so nothing here opens a socket. Covered: the
consent gate, the size and hash checks, cancellation, the order of writes (the
record last), the cleanup after every failure, the replace-and-restore of an older
version, the redirect rule, the shape of the one real request, and the import
rule (the package does not load the downloader).
"""

from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tests.support.cli import cli_env
from trigger_designer.core.modules import (
    Consent,
    ModuleError,
    ModuleStore,
    consent_summary,
    downloader,
    install_module,
    parse_manifest,
)
from trigger_designer.core.modules.consent import size_text

pytestmark = pytest.mark.unit

# 153,600 + 440 bytes: the model arrives in three reads, the vocabulary in one.
PAYLOAD = {"model.bin": bytes(range(256)) * 600, "vocab.txt": b"alpha\nbeta\n" * 40}


def manifest_for(
    payload: dict = PAYLOAD, *, version: str = "1.0.0", module_id: str = "fuzzy-model"
):
    return parse_manifest(
        {
            "id": module_id,
            "name": "Fuzzy match model",
            "version": version,
            "description": "A local model for the install tests.",
            "license": "MIT",
            "files": [
                {
                    "name": name,
                    "url": f"https://files.example.com/{module_id}/{name}",
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in payload.items()
            ],
        }
    )


class FakeOpener:
    """Stands in for the network: serves ``served[file name]`` for each URL."""

    def __init__(self, served: dict) -> None:
        self.served = served
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float):
        self.calls.append((url, timeout))
        return io.BytesIO(self.served[url.rsplit("/", 1)[-1]])


def install(manifest, store, *, served: dict | None = None, **options):
    opener = FakeOpener(PAYLOAD if served is None else served)
    installed = install_module(
        manifest, Consent.granted(manifest), store, opener=opener, **options
    )
    return installed, opener


def assert_no_residue(root: Path, module_id: str) -> None:
    assert not (root / module_id).exists()
    assert not (root / ".partial").exists()


# ----------------------------------------------------------------- the happy path
def test_a_consented_install_downloads_checks_and_writes_the_record_last(
    tmp_path, monkeypatch
):
    root = tmp_path / "modules"
    store = ModuleStore(root)
    manifest = manifest_for()
    progress_calls: list[tuple[int, int]] = []
    names_when_recorded: list[set[str]] = []
    write_record = downloader.write_json_atomic

    def record_spy(path, obj):
        names_when_recorded.append({item.name for item in Path(path).parent.iterdir()})
        write_record(path, obj)

    monkeypatch.setattr(downloader, "write_json_atomic", record_spy)
    installed, opener = install(
        manifest,
        store,
        progress=lambda done, total: progress_calls.append((done, total)),
    )

    total = manifest.total_size
    assert installed.path == root / "fuzzy-model"
    assert installed.size_bytes == total
    assert installed == store.get("fuzzy-model")
    # every file was in place before the record was written
    assert names_when_recorded == [set(PAYLOAD)]
    assert len(progress_calls) == 4  # three reads of model.bin, one of vocab.txt
    assert progress_calls[-1] == (total, total)
    assert [done for done, _ in progress_calls] == sorted(
        done for done, _ in progress_calls
    )
    assert [url for url, _ in opener.calls] == [
        "https://files.example.com/fuzzy-model/model.bin",
        "https://files.example.com/fuzzy-model/vocab.txt",
    ]
    assert all(timeout == 30.0 for _, timeout in opener.calls)
    assert store.verify("fuzzy-model").ok
    assert not (root / ".partial").exists()


# ------------------------------------------------------------------ the consent
def test_no_consent_means_nothing_is_downloaded(tmp_path):
    root = tmp_path / "modules"
    opener = FakeOpener(PAYLOAD)
    with pytest.raises(ModuleError) as caught:
        install_module(manifest_for(), None, ModuleStore(root), opener=opener)
    assert caught.value.code == "TD-MOD-003"
    assert opener.calls == []
    assert not root.exists()


def test_consent_for_another_manifest_is_refused(tmp_path):
    root = tmp_path / "modules"
    opener = FakeOpener(PAYLOAD)
    other = manifest_for(version="9.9.9")
    with pytest.raises(ModuleError) as caught:
        install_module(
            manifest_for(), Consent.granted(other), ModuleStore(root), opener=opener
        )
    assert caught.value.code == "TD-MOD-003"
    assert opener.calls == []


# ------------------------------------------------------------ checks and cleanup
def test_a_file_with_the_wrong_hash_is_discarded_and_nothing_is_installed(tmp_path):
    root = tmp_path / "modules"
    served = {**PAYLOAD, "vocab.txt": b"Z" * len(PAYLOAD["vocab.txt"])}
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(), ModuleStore(root), served=served)
    assert caught.value.code == "TD-MOD-007"
    assert_no_residue(root, "fuzzy-model")
    assert ModuleStore(root).installed() == []


def test_more_bytes_than_the_manifest_allows_are_refused(tmp_path):
    root = tmp_path / "modules"
    served = {**PAYLOAD, "vocab.txt": PAYLOAD["vocab.txt"] + b"!"}
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(), ModuleStore(root), served=served)
    assert caught.value.code == "TD-MOD-006"
    assert_no_residue(root, "fuzzy-model")


def test_fewer_bytes_than_the_manifest_says_are_refused(tmp_path):
    root = tmp_path / "modules"
    served = {**PAYLOAD, "vocab.txt": PAYLOAD["vocab.txt"][:-1]}
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(), ModuleStore(root), served=served)
    assert caught.value.code == "TD-MOD-006"
    assert_no_residue(root, "fuzzy-model")


def test_cancel_before_anything_is_written_leaves_nothing(tmp_path):
    root = tmp_path / "modules"
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(), ModuleStore(root), cancel=lambda: True)
    assert caught.value.code == "TD-MOD-009"
    assert_no_residue(root, "fuzzy-model")


def test_cancel_between_chunks_leaves_nothing(tmp_path):
    root = tmp_path / "modules"
    seen: list[int] = []
    with pytest.raises(ModuleError) as caught:
        install(
            manifest_for(),
            ModuleStore(root),
            progress=lambda done, total: seen.append(done),
            cancel=lambda: len(seen) >= 2,
        )
    assert caught.value.code == "TD-MOD-009"
    assert len(seen) == 2
    assert_no_residue(root, "fuzzy-model")


@pytest.mark.parametrize(
    "failure",
    [
        OSError("connection reset"),
        urllib.error.URLError("no route to host"),
        TimeoutError("timed out"),
    ],
)
def test_a_connection_that_cannot_be_opened_is_a_download_error(tmp_path, failure):
    root = tmp_path / "modules"
    manifest = manifest_for()

    def unreachable(url, timeout):
        raise failure

    with pytest.raises(ModuleError) as caught:
        install_module(
            manifest,
            Consent.granted(manifest),
            ModuleStore(root),
            opener=unreachable,
        )
    assert caught.value.code == "TD-MOD-005"
    assert_no_residue(root, "fuzzy-model")


class DroppedStream:
    """Serves one chunk, then drops the connection the way a network reset does."""

    def __init__(self) -> None:
        self.reads = 0

    def read(self, size: int) -> bytes:
        self.reads += 1
        if self.reads == 1:
            return b"x" * 1000
        raise ConnectionResetError("connection reset by peer")

    def close(self) -> None:
        pass


def test_a_connection_dropped_mid_download_is_a_download_error(tmp_path):
    root = tmp_path / "modules"
    manifest = manifest_for()
    with pytest.raises(ModuleError) as caught:
        install_module(
            manifest,
            Consent.granted(manifest),
            ModuleStore(root),
            opener=lambda url, timeout: DroppedStream(),
        )
    assert caught.value.code == "TD-MOD-005"
    assert_no_residue(root, "fuzzy-model")


def test_a_disk_error_while_writing_is_an_install_error(tmp_path, monkeypatch):
    root = tmp_path / "modules"

    def no_space(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(downloader, "open", no_space, raising=False)
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(), ModuleStore(root))
    assert caught.value.code == "TD-MOD-008"
    assert "No space left on device" in caught.value.message
    assert_no_residue(root, "fuzzy-model")


# ------------------------------------------------------------ reinstall and swap
def test_a_reinstall_replaces_the_old_version(tmp_path):
    root = tmp_path / "modules"
    store = ModuleStore(root)
    install(manifest_for(), store)
    second = {"model.bin": b"second model " * 100}
    install(manifest_for(second, version="2.0.0"), store, served=second)
    assert store.get("fuzzy-model").version == "2.0.0"
    names = sorted(item.name for item in (root / "fuzzy-model").iterdir())
    assert names == ["model.bin", "module.json"]  # the old vocab.txt is gone
    assert store.verify("fuzzy-model").ok
    assert not (root / ".partial").exists()


def test_a_failing_reinstall_keeps_the_old_version(tmp_path):
    root = tmp_path / "modules"
    store = ModuleStore(root)
    install(manifest_for(), store)
    second = {"model.bin": b"second model " * 100}
    wrong = {"model.bin": b"x" * len(second["model.bin"])}
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(second, version="2.0.0"), store, served=wrong)
    assert caught.value.code == "TD-MOD-007"
    assert store.get("fuzzy-model").version == "1.0.0"
    assert store.verify("fuzzy-model").ok
    assert not (root / ".partial").exists()


def test_a_failing_commit_puts_the_old_version_back(tmp_path, monkeypatch):
    root = tmp_path / "modules"
    store = ModuleStore(root)
    install(manifest_for(), store)
    second = {"model.bin": b"second model " * 100}

    def refuse(path, obj):
        raise OSError(13, "Access is denied")

    monkeypatch.setattr(downloader, "write_json_atomic", refuse)
    with pytest.raises(ModuleError) as caught:
        install(manifest_for(second, version="2.0.0"), store, served=second)
    assert caught.value.code == "TD-MOD-008"
    assert store.get("fuzzy-model").version == "1.0.0"
    assert store.verify("fuzzy-model").ok
    assert not (root / ".partial").exists()


# ----------------------------------------------------------- network rules
def test_a_redirect_to_another_host_or_to_plain_http_is_refused():
    handler = downloader._SameHostRedirect()
    request = urllib.request.Request("https://files.example.com/fuzzy-model/model.bin")
    for target in (
        "https://evil.example.net/model.bin",
        "http://files.example.com/model.bin",
        "https://user@files.example.com/model.bin",
    ):
        with pytest.raises(ModuleError) as caught:
            handler.redirect_request(request, None, 302, "Found", {}, target)
        assert caught.value.code == "TD-MOD-004", target


def test_a_redirect_within_the_same_secure_host_is_followed():
    handler = downloader._SameHostRedirect()
    request = urllib.request.Request("https://files.example.com/fuzzy-model/model.bin")
    followed = handler.redirect_request(
        request, None, 302, "Found", {}, "/cdn/model.bin"
    )
    assert followed.full_url == "https://files.example.com/cdn/model.bin"


def test_the_one_real_request_is_a_plain_get_with_a_generic_user_agent(monkeypatch):
    seen: dict = {}

    class RecordingOpener:
        def open(self, request, timeout):
            seen["request"] = request
            seen["timeout"] = timeout
            return io.BytesIO(b"")

    def build(*handlers):
        seen["handlers"] = handlers
        return RecordingOpener()

    monkeypatch.setattr(urllib.request, "build_opener", build)
    downloader._open_url("https://files.example.com/fuzzy-model/model.bin", 12.5)
    request = seen["request"]
    assert request.get_method() == "GET"
    assert request.headers["User-agent"] == "TriggerDesigner-modules/1"
    assert request.headers["Accept-encoding"] == "identity"
    assert not request.has_header("Cookie")
    assert not request.has_header("Authorization")
    assert seen["timeout"] == 12.5
    assert any(
        isinstance(handler, downloader._SameHostRedirect)
        for handler in seen["handlers"]
    )


def test_importing_the_package_does_not_load_the_downloader(tmp_path):
    code = (
        "import sys\n"
        "import trigger_designer.core.modules\n"
        "print('trigger_designer.core.modules.downloader' in sys.modules)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=cli_env(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False"


# --------------------------------------------------------------- consent text
def test_the_consent_summary_names_the_hosts_size_and_hashes():
    manifest = manifest_for()
    summary = consent_summary(manifest)
    assert summary.module_id == "fuzzy-model"
    assert summary.hosts == ("files.example.com",)
    assert summary.total_size == manifest.total_size
    assert summary.total_size_text == size_text(manifest.total_size)
    assert [item[0] for item in summary.files] == ["model.bin", "vocab.txt"]
    assert summary.files[0][3] == hashlib.sha256(PAYLOAD["model.bin"]).hexdigest()
    assert "files.example.com" in summary.notice
    assert "2 files" in summary.notice
    assert summary.total_size_text in summary.notice
    assert summary.notice.endswith("You can remove the module at any time.")


def test_size_text_uses_decimal_units():
    assert size_text(512) == "512 B"
    assert size_text(1_200) == "1.2 KB"
    assert size_text(999_000) == "999.0 KB"
    assert size_text(1_000_000) == "1.0 MB"
    assert size_text(12_300_000) == "12.3 MB"
    assert size_text(1_500_000_000) == "1.5 GB"


def test_a_consent_records_the_fingerprint_of_its_manifest():
    manifest = manifest_for()
    consent = Consent.granted(manifest)
    assert consent.fingerprint == manifest.fingerprint()
    assert consent.accepted_at.endswith("Z")
