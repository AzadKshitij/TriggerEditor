"""ColumnPicker: compact display, popup checklist and bulk actions."""

from __future__ import annotations

from qtpy.QtWidgets import QLabel

from trigger_designer.qt.widgets.common import ColumnPicker


def test_picker_selects_emits_and_filters(qtbot) -> None:
    picker = ColumnPicker(("Account", "Customer", "Region"), ("Account",))
    qtbot.addWidget(picker)
    changes = []
    picker.changed.connect(changes.append)
    picker._ensure_popup()

    assert picker.checked() == ["Account"]
    picker._checklist.checkboxes["Customer"].click()
    assert picker.checked() == ["Account", "Customer"]
    assert changes[-1] == ["Account", "Customer"]

    tokens = [
        label.text()
        for label in picker.findChildren(QLabel)
        if label.objectName() == "ColumnToken" and not label.isHidden()
    ]
    assert tokens == ["Account", "Customer"]
    assert all(not label.isWindow() for label in picker.findChildren(QLabel))

    picker._search.setText("reg")
    assert picker._checklist.checkboxes["Region"].isHidden() is False
    assert picker._checklist.checkboxes["Account"].isHidden() is True

    picker._set_all(False)
    assert picker.checked() == []
    picker._search.clear()
    picker._set_all(True)
    assert picker.checked() == ["Account", "Customer", "Region"]


def test_picker_set_columns_keeps_only_surviving_values(qtbot) -> None:
    picker = ColumnPicker(("a", "b"), ("a", "b"))
    qtbot.addWidget(picker)
    picker.setColumns(("b", "c"), ("a", "b"))
    assert picker.checked() == ["b"]
    picker.setChecked(["c"])
    assert picker.checked() == ["c"]
