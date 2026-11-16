#!/usr/bin/env python3
"""First install shows the sample workflow instead of a dead dialog (issue #31).

A fresh install has no recent projects, so the welcome dialog's recents list
is empty. Two things must hold:

* the dialog always offers the bundled example when the caller provides one,
  and clicking it sets action ``"sample"`` and accepts;
* the sample materializes into the app-data directory with every stored path
  rewritten there - the bundle itself is read-only and must never be written.
"""

import json

from qtpy.QtWidgets import QApplication

from trigger_designer.qt.dialogs.welcome_dialog import SampleInfo, WelcomeDialog
from trigger_designer.qt.helpers.sample_workflow import (
    SAMPLE_NAME,
    bundled_sample_dir,
    materialize_sample,
)
from trigger_designer.qt.preferences import app_data_dir

_APP = QApplication.instance() or QApplication([])

_SAMPLE = SampleInfo("Sample title", "Sample description")


def _cleanup(path) -> None:
    path.hide()
    path.deleteLater()
    _APP.processEvents()


def test_dialog_offers_the_example() -> None:
    dialog = WelcomeDialog([], parent=None, sample=_SAMPLE)
    try:
        assert dialog.sample_panel is not None
        assert dialog.open_sample_button.text() == "Open Example"
        dialog.open_sample_button.click()
        assert dialog.action == "sample"
        assert dialog.result() == dialog.DialogCode.Accepted
    finally:
        _cleanup(dialog)


def test_dialog_without_a_sample_hides_the_row() -> None:
    dialog = WelcomeDialog([], sample=None)
    try:
        assert dialog.sample_panel is None
        assert not hasattr(dialog, "open_sample_button")
    finally:
        _cleanup(dialog)


def test_recent_row_keeps_its_action() -> None:
    dialog = WelcomeDialog(["C:/tmp/example.tds"], sample=_SAMPLE)
    try:
        dialog.new_button.click()
        assert dialog.action == "new"
    finally:
        _cleanup(dialog)


def test_materialize_copies_and_rewrites() -> None:
    target = app_data_dir() / "samples" / SAMPLE_NAME
    data_file = target / "data" / "ae-2026-03.csv"
    for stale in (target / "ae_winter_watch.tds", data_file):
        stale.unlink(missing_ok=True)

    tds = materialize_sample()
    try:
        assert tds.is_file()
        assert (target / "output").is_dir()
        assert data_file.is_file()
        assert len(list((target / "data").glob("*.csv"))) == 12

        payload = json.loads(tds.read_bytes())
        root = str(target).replace("\\", "/")
        absolute = [
            value
            for node in payload["nodes"]
            if isinstance(node.get("content"), dict)
            for value in _iter_path_strings(node["content"])
        ]
        assert absolute, "the sample carries no paths to rewrite"
        for value in absolute:
            assert "Example_3_AE_Winter_Watch" not in value
            assert "<you>" not in value
            assert value.replace("\\", "/").startswith(root)
    finally:
        # The bundle must never be written.
        assert bundled_sample_dir().joinpath("ae_winter_watch.tds").read_bytes()


def _iter_path_strings(content: dict):
    for value in content.values():
        if isinstance(value, str) and (
            (":" in value[:3]) or value.startswith("/") or value.lower().endswith(".csv")
        ):
            yield value
        if isinstance(value, dict):
            yield from _iter_path_strings(value)


def test_materialize_keeps_the_users_copy() -> None:
    tds = materialize_sample()
    marker = tds.read_bytes()
    tds.write_bytes(marker + b" ")
    second = materialize_sample()
    try:
        assert second == tds
        assert second.read_bytes().endswith(b" ")
    finally:
        second.write_bytes(marker)


def test_welcome_uses_the_sample_action() -> None:
    """_open_sample_workflow opens the materialized document."""
    from trigger_designer.qt.main_window import TriggerWindow

    window = TriggerWindow()
    try:
        window.show()
        _APP.processEvents()
        opened: list[str] = []
        original_open = window.openFile

        def record(path):
            opened.append(str(path))

        window.openFile = record  # type: ignore[method-assign]
        window._open_sample_workflow()
        assert opened
        assert opened[0].endswith("ae_winter_watch.tds")
        assert app_data_dir().parts[-1] in opened[0]
    finally:
        window.openFile = original_open  # type: ignore[method-assign]
        window.hide()
        window.deleteLater()
        _APP.processEvents()
