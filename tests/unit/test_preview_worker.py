#!/usr/bin/env python3
"""PreviewRequestController: id/stale rules, busy flag, real-thread round trips."""

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.models import preview_worker
from trigger_designer.qt.models.preview_sampling import (
    PreviewWindow,
    collect_preview,
)
from trigger_designer.qt.models.preview_worker import PreviewRequestController

_APP = QApplication.instance() or QApplication([])


def _empty_window() -> PreviewWindow:
    return PreviewWindow(
        frame=pl.DataFrame({"n": pl.Series([], dtype=pl.Int64)}),
        total_rows=0,
        limited=False,
        is_lazy=False,
    )


def _wait_until(predicate, timeout_ms: int = 10_000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    QApplication.processEvents()
    return predicate()


# -- id / staleness rules (handlers called directly) ------------------------


def test_newest_collect_result_is_forwarded():
    controller = PreviewRequestController()
    received = []
    controller.previewReady.connect(received.append)
    controller._newest_id = 7
    window = _empty_window()

    controller._on_collect_ok(7, window)

    assert received == [window]


def test_superseded_collect_result_is_dropped():
    controller = PreviewRequestController()
    received = []
    controller.previewReady.connect(received.append)
    controller._newest_id = 8

    controller._on_collect_ok(7, _empty_window())

    assert received == []


def test_superseded_failure_is_dropped_and_newest_is_reported():
    controller = PreviewRequestController()
    failures = []
    controller.failed.connect(failures.append)
    controller._newest_id = 5

    controller._on_collect_failed(4, "old")
    assert failures == []

    controller._on_collect_failed(5, "boom")
    assert failures == ["boom"]


def test_count_results_follow_the_newest_id():
    controller = PreviewRequestController()
    counts = []
    controller.countReady.connect(counts.append)
    controller._newest_id = 3

    controller._on_count_ok(2, 10)  # superseded -> dropped
    controller._on_count_ok(3, 12)

    assert counts == [12]


def test_count_failure_reports_minus_one_for_the_newest_only():
    controller = PreviewRequestController()
    counts = []
    controller.countReady.connect(counts.append)
    controller._newest_id = 3

    controller._on_count_failed(2, "old")
    assert counts == []

    controller._on_count_failed(3, "boom")
    assert counts == [-1]


def test_requests_coalesce_to_the_newest_pending_payload_while_busy():
    controller = PreviewRequestController()
    controller._collect_worker = object()  # pretend a collect is in flight

    first = controller.request("first")
    second = controller.request("second")

    assert first != second
    assert controller._pending == (second, "second")
    assert controller._newest_id == second
    assert controller.busy is True


# -- real-thread round trips -------------------------------------------------


def test_collect_round_trip_reports_busy_and_result():
    controller = PreviewRequestController(max_rows=10)
    previews = []
    busy_states = []
    controller.previewReady.connect(previews.append)
    controller.busyChanged.connect(busy_states.append)

    request_id = controller.request(pl.DataFrame({"n": range(100)}))

    assert request_id == 1
    assert controller.busy is True
    assert _wait_until(lambda: previews and controller.busy is False)

    window = previews[0]
    assert window.frame.height == 10
    assert window.total_rows == 100
    assert window.limited is True
    assert window.is_lazy is False
    assert busy_states[0] is True
    assert busy_states[-1] is False


def test_truncated_lazy_request_counts_in_the_background():
    controller = PreviewRequestController(max_rows=5)
    previews = []
    counts = []
    controller.previewReady.connect(previews.append)
    controller.countReady.connect(counts.append)

    controller.request(pl.DataFrame({"n": range(50)}).lazy())

    assert _wait_until(lambda: previews)
    assert previews[0].limited and previews[0].is_lazy
    assert _wait_until(lambda: counts == [50])
    # every worker is released once its thread stops, not leaked
    assert _wait_until(lambda: not preview_worker._LIVE_WORKERS)


def test_unlimited_lazy_request_never_starts_a_count():
    controller = PreviewRequestController(max_rows=1000)
    previews = []
    counts = []
    controller.previewReady.connect(previews.append)
    controller.countReady.connect(counts.append)

    controller.request(pl.DataFrame({"n": range(10)}).lazy())

    assert _wait_until(lambda: previews)
    assert previews[0].limited is False
    # every worker released and nothing counted: no count worker was started
    assert _wait_until(lambda: not preview_worker._LIVE_WORKERS)
    assert counts == []

    eager = collect_preview(pl.DataFrame({"n": range(10)}), max_rows=1000)
    assert eager.limited is False
