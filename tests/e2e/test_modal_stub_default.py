"""The e2e layer stubs modal dialogs without each test asking for it."""

from __future__ import annotations

from trigger_designer.qt import design_window


def test_progress_dialog_is_stubbed_by_default() -> None:
    dialog = design_window.make_progress_dialog()
    assert type(dialog).__name__ == "_NullProgressDialog"


def test_requesting_the_fixture_again_shares_the_default_capture(
    no_modal_dialogs,
) -> None:
    assert set(no_modal_dialogs) == {"warnings", "run_code"}
