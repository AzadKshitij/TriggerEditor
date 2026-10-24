"""ColumnPicker: trigger, search, visible bulk actions and single mode."""

from __future__ import annotations

from qtpy.QtWidgets import QLabel

from trigger_designer.qt.widgets.common import ColumnPicker


def test_picker_search_toggle_and_emit(qtbot) -> None:
    picker = ColumnPicker(("Account", "Customer", "Region"), ("Account",))
    qtbot.addWidget(picker)
    changes = []
    picker.changed.connect(changes.append)
    picker.open_popup()
    qtbot.addWidget(picker._popup)

    assert picker.checked() == ["Account"]
    assert picker.is_open()
    picker._popup.search.setText("reg")
    assert picker.visible_names() == ["Region"]
    assert picker._popup.list.model().rowCount() == 1

    picker._toggle_name("Region")
    assert picker.checked() == ["Account", "Region"]
    assert changes[-1] == ["Account", "Region"]
    assert picker.is_open()
    picker.close_popup()
    assert not picker.is_open()


def test_picker_trigger_tokens_and_overflow(qtbot) -> None:
    picker = ColumnPicker(
        ("Account", "Customer", "Region", "Amount"),
        ("Account", "Customer", "Region", "Amount"),
    )
    qtbot.addWidget(picker)
    token_labels = [
        label
        for label in picker.findChildren(QLabel)
        if label.objectName() == "ColumnToken"
    ]
    assert token_labels[0].text() == "Account"
    assert {label.toolTip() for label in token_labels} == {"Account", "Customer"}
    assert any(label.text() == "+2" for label in picker.findChildren(QLabel))


def test_picker_bulk_actions_only_touch_visible_rows(qtbot) -> None:
    picker = ColumnPicker(("Account", "Customer", "Region"), ("Account",))
    qtbot.addWidget(picker)
    picker.open_popup()
    qtbot.addWidget(picker._popup)
    picker._popup.search.setText("reg")
    picker._popup.all_button.click()
    assert picker.checked() == ["Account", "Region"]
    picker._popup.none_button.click()
    assert picker.checked() == ["Account"]
    picker.close_popup()


def test_picker_set_columns_keeps_only_surviving_values(qtbot) -> None:
    picker = ColumnPicker(("a", "b"), ("a", "b"))
    qtbot.addWidget(picker)
    picker.setColumns(("b", "c"), ("a", "b"))
    assert picker.checked() == ["b"]
    picker.setChecked(["c"])
    assert picker.checked() == ["c"]


def test_single_picker_closes_and_blank_clears(qtbot) -> None:
    picker = ColumnPicker(
        ("A", "B"),
        (),
        single=True,
        allow_blank=True,
        placeholder="Choose column...",
    )
    qtbot.addWidget(picker)
    picker.open_popup()
    qtbot.addWidget(picker._popup)
    picker._toggle_name("A")
    assert picker.checked() == ["A"]
    assert not picker.is_open()

    picker.open_popup()
    picker._toggle_name("")
    assert picker.checked() == []
    assert not picker.is_open()
