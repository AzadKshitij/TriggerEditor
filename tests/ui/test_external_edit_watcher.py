"""ExternalEditWatcher: a ``.tds`` another tool rewrites is reported once (AI plan, phase 4)."""

from __future__ import annotations

import hashlib

import pytest

from trigger_designer.core.authoring import Editor, new_workflow
from trigger_designer.core.headless.atomic import write_bytes_atomic
from trigger_designer.core.headless.params import dump_workflow
from trigger_designer.qt.helpers.external_edit_watcher import ExternalEditWatcher

pytestmark = pytest.mark.ui

#: Short intervals keep the timer-driven tests quick.
DEBOUNCE_MS = 20
RETRY_MS = 40
#: Long enough for a late event or a stray retry to show up before we look again.
QUIET_MS = 300


def _workflow(tmp_path, *, nodes: int = 0) -> bytes:
    editor = Editor(new_workflow(), base_dir=str(tmp_path))
    for _ in range(nodes):
        editor.add_node("preparation.sort")
    return dump_workflow(editor.data)


@pytest.fixture
def make_watcher():
    """Build watchers and stop each one on teardown.

    Windows keeps a handle on a watched folder, so ``tmp_path`` cannot be
    removed while a watcher still holds it.
    """
    made: list[ExternalEditWatcher] = []

    def make(**overrides) -> ExternalEditWatcher:
        options = {"debounce_ms": DEBOUNCE_MS, "retry_ms": RETRY_MS, **overrides}
        watcher = ExternalEditWatcher(**options)
        made.append(watcher)
        return watcher

    yield make
    for watcher in made:
        watcher.stop()


@pytest.fixture
def flow(tmp_path):
    """A workflow file on disk, and the bytes the editor holds for it."""
    path = tmp_path / "flow.tds"
    base = _workflow(tmp_path)
    path.write_bytes(base)
    return path, base


def _watching(make_watcher, path, base, **overrides) -> ExternalEditWatcher:
    watcher = make_watcher(**overrides)
    watcher.watch(str(path), base)
    return watcher


def test_identical_bytes_are_not_a_change(make_watcher, flow):
    path, base = flow
    watcher = _watching(make_watcher, path, base)

    assert watcher.check_now() is None


def test_an_atomic_replace_that_adds_a_node_is_a_change(make_watcher, flow, tmp_path):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    new = _workflow(tmp_path, nodes=1)

    write_bytes_atomic(path, new)

    change = watcher.check_now()
    assert change is not None
    assert change.status == "changed"
    assert change.sha256 == hashlib.sha256(new).hexdigest()


def test_a_rewrite_is_reported_once_and_the_same_bytes_again_are_silent(
    make_watcher, flow, tmp_path, qtbot
):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    new = _workflow(tmp_path, nodes=1)

    with qtbot.waitSignal(watcher.changeDetected, timeout=5000) as blocker:
        write_bytes_atomic(path, new)
    assert blocker.args[0].status == "changed"

    reports = []
    watcher.changeDetected.connect(reports.append)
    write_bytes_atomic(path, new)  # the same bytes again
    qtbot.wait(QUIET_MS)
    assert reports == []


def test_accepting_bytes_makes_them_the_baseline(make_watcher, flow, tmp_path):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    new = _workflow(tmp_path, nodes=1)
    write_bytes_atomic(path, new)
    assert watcher.check_now() is not None

    watcher.accept(new)

    assert watcher.baseline == new
    assert watcher.check_now() is None


def test_dismissed_content_is_never_reported(make_watcher, flow, tmp_path, qtbot):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    reports = []
    watcher.changeDetected.connect(reports.append)
    new = _workflow(tmp_path, nodes=1)
    write_bytes_atomic(path, new)
    change = watcher.check_now()
    assert change is not None

    watcher.dismiss(change.sha256)

    assert watcher.check_now() is None
    write_bytes_atomic(path, new)  # the dismissed content comes back
    qtbot.wait(QUIET_MS)
    assert reports == []


def test_a_truncated_file_is_reported_once_it_stays_invalid(
    make_watcher, flow, tmp_path, qtbot
):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    new = _workflow(tmp_path, nodes=1)

    with qtbot.waitSignal(watcher.changeDetected, timeout=5000) as blocker:
        write_bytes_atomic(path, new[: len(new) // 2])
    assert blocker.args[0].status == "invalid"


def test_a_half_written_file_completed_in_time_is_not_reported_as_invalid(
    make_watcher, flow, tmp_path, qtbot
):
    path, base = flow
    watcher = _watching(make_watcher, path, base, retry_ms=300)
    reports = []
    watcher.changeDetected.connect(reports.append)
    new = _workflow(tmp_path, nodes=1)

    write_bytes_atomic(path, new[: len(new) // 2])
    qtbot.wait(4 * DEBOUNCE_MS)  # the first look has seen the half-written file
    write_bytes_atomic(path, new)  # the writer finishes before the retry
    qtbot.waitUntil(lambda: len(reports) == 1, timeout=5000)
    qtbot.wait(700)  # past the retry: it must not add an invalid report
    assert [report.status for report in reports] == ["changed"]


def test_a_deleted_file_is_no_change_and_a_re_created_one_is_noticed(
    make_watcher, flow, tmp_path, qtbot
):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    reports = []
    watcher.changeDetected.connect(reports.append)

    path.unlink()
    assert watcher.check_now() is None
    qtbot.wait(QUIET_MS)
    assert reports == []

    path.write_bytes(_workflow(tmp_path, nodes=1))
    qtbot.waitUntil(lambda: len(reports) == 1, timeout=5000)
    assert reports[0].status == "changed"


def test_watching_nothing_stops_the_watch(make_watcher, flow, tmp_path, qtbot):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    reports = []
    watcher.changeDetected.connect(reports.append)

    watcher.watch(None, None)
    assert watcher.path is None
    assert watcher.baseline is None
    watcher.watch(str(path), None)
    assert watcher.path is None

    write_bytes_atomic(path, _workflow(tmp_path, nodes=1))
    qtbot.wait(QUIET_MS)
    assert reports == []
    assert watcher.check_now() is None


def test_stop_releases_the_watch_and_a_later_watch_works_again(
    make_watcher, flow, tmp_path, qtbot
):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    reports = []
    watcher.changeDetected.connect(reports.append)

    watcher.stop()
    assert watcher.path is None
    write_bytes_atomic(path, _workflow(tmp_path, nodes=1))
    qtbot.wait(QUIET_MS)
    assert reports == []

    watcher.watch(str(path), base)
    with qtbot.waitSignal(watcher.changeDetected, timeout=5000) as blocker:
        write_bytes_atomic(path, _workflow(tmp_path, nodes=2))
    assert blocker.args[0].status == "changed"


def test_the_apps_own_save_is_never_reported(make_watcher, flow, tmp_path, qtbot):
    path, base = flow
    watcher = _watching(make_watcher, path, base)
    reports = []
    watcher.changeDetected.connect(reports.append)
    saved = _workflow(tmp_path, nodes=1)

    write_bytes_atomic(path, saved)  # what TriggerScene.saveToFile does
    watcher.accept(saved)  # the owner takes the bytes it has just written

    qtbot.wait(QUIET_MS)
    assert reports == []
    assert watcher.check_now() is None
