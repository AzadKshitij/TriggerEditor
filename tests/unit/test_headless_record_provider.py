"""The headless runner installs the run-record provider for the run only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from trigger_designer.core.audit.recorder import (
    get_run_record_provider,
    set_run_record_provider,
)
from trigger_designer.core.headless.runner import _Run


class FakeRecorder:
    def __init__(self, data=None, fail=False):
        self.data = data or {"status": "running", "nodes": [{"node_id": 1}]}
        self.fail = fail

    def snapshot(self):
        if self.fail:
            raise RuntimeError("boom")
        return self.data


def _run(no_record=False, recorder=None):
    run = object.__new__(_Run)
    run.opts = SimpleNamespace(no_record=no_record)
    run.recorder = recorder
    run._provider_installed = False
    return run


@pytest.fixture(autouse=True)
def _clean():
    set_run_record_provider(None)
    yield
    set_run_record_provider(None)


def test_provider_is_installed_then_cleared() -> None:
    run = _run(recorder=FakeRecorder())
    run._install_record_provider()
    provider = get_run_record_provider()
    assert provider is not None
    assert provider()["nodes"][0]["node_id"] == 1
    run._clear_record_provider()
    assert get_run_record_provider() is None
    run._clear_record_provider()  # idempotent


def test_cleanup_clears_the_provider_on_failure_paths() -> None:
    run = _run(recorder=FakeRecorder())
    run.sup = run.plan = run.lock = None
    run._install_record_provider()
    run.cleanup()
    assert get_run_record_provider() is None


def test_no_record_installs_nothing() -> None:
    run = _run(no_record=True, recorder=FakeRecorder())
    run._install_record_provider()
    assert get_run_record_provider() is None


def test_a_failing_snapshot_returns_none_not_an_error() -> None:
    run = _run(recorder=FakeRecorder(fail=True))
    run._install_record_provider()
    assert get_run_record_provider()() is None


def test_clearing_does_not_touch_a_provider_it_did_not_install() -> None:
    other = lambda: {"status": "running"}
    set_run_record_provider(other)
    _run(recorder=FakeRecorder())._clear_record_provider()
    assert get_run_record_provider() is other
