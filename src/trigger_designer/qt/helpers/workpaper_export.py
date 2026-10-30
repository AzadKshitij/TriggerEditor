"""File > Export Workpaper...: a workpaper of the last recorded run.

The summary of one whole run (one row per audit test), its run log and the
workflow, written by the Qt-free ``write_run_workpaper``. Exceptions listings for
a single test come from the Workpaper Output node instead.
"""

from __future__ import annotations

import os
from typing import Any

from loguru import logger
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.constants import VERSION
from trigger_designer.core.workpaper import node_logic, write_run_workpaper
from trigger_designer.qt.helpers.audit_bridge import store_from_preferences
from trigger_designer.qt.helpers.workflow_snapshot import collect_scene_workflow
from trigger_designer.qt.preferences import get_preferences
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    FormRow,
    IconButton,
    NoWheelComboBox,
)

TITLE = "Export workpaper"
NO_RECORD = (
    "There is no recorded run for this workflow yet.\n\n"
    "Run the workflow first (and keep run recording on in Preferences), then export the "
    "workpaper."
)
_FIELDS = (
    ("workpaper_ref", "Reference", "e.g. C.3.1"),
    ("client", "Client", ""),
    ("engagement", "Engagement", ""),
    ("period", "Period", ""),
    ("preparer", "Prepared by", ""),
)


def engagement_defaults() -> dict[str, str]:
    prefs = get_preferences()
    return {
        "client_name": str(prefs.get("engagement/client_name", "") or ""),
        "engagement_name": str(prefs.get("engagement/engagement_name", "") or ""),
        "period": str(prefs.get("engagement/period", "") or ""),
        "preparer": str(prefs.get("engagement/preparer", "") or ""),
        "logo_path": str(prefs.get("engagement/logo_path", "") or ""),
    }


def default_output_path(workflow_path: str | None) -> str:
    """Suggested file: ``<workflow name> workpaper.xlsx`` in the last used folder."""
    stem = os.path.splitext(os.path.basename(workflow_path or ""))[0] or "Workflow"
    folder = str(get_preferences().get("export/workpaper_dir", "") or "")
    if not folder and workflow_path:
        folder = os.path.dirname(workflow_path)
    return (
        os.path.join(folder, f"{stem} workpaper.xlsx")
        if folder
        else f"{stem} workpaper.xlsx"
    )


class WorkpaperExportDialog(QDialog):
    """Asks for the engagement details and the file; nothing else."""

    def __init__(self, parent: QWidget | None, output_path: str) -> None:
        super().__init__(parent)
        self.setObjectName("WorkpaperExportDialog")
        self.setWindowTitle(TITLE)
        self.setModal(True)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        defaults = engagement_defaults()
        inherited = {
            "client": defaults["client_name"],
            "engagement": defaults["engagement_name"],
            "period": defaults["period"],
            "preparer": defaults["preparer"],
        }

        file_section = ConfigSection("File")
        self.path_edit = QLineEdit(output_path)
        self.path_edit.setMinimumHeight(30)
        self.path_edit.setAccessibleName("Workpaper file")
        browse = IconButton.themed("Browse for save location")
        browse.clicked.connect(self.browse)
        file_section.addWidget(
            FormRow("File", self.path_edit, label_width=96, action=browse)
        )
        self.if_exists = NoWheelComboBox()
        self.if_exists.setMinimumHeight(30)
        for value, label in node_logic.IF_EXISTS_LABELS:
            self.if_exists.addItem(label, value)
        file_section.addWidget(FormRow("If it exists", self.if_exists, label_width=96))
        layout.addWidget(file_section)

        details = ConfigSection("Engagement")
        self.edits: dict[str, QLineEdit] = {}
        for key, label, placeholder in _FIELDS:
            edit = QLineEdit()
            edit.setMinimumHeight(30)
            edit.setAccessibleName(label)
            edit.setPlaceholderText(inherited.get(key) or placeholder)
            self.edits[key] = edit
            details.addWidget(FormRow(label, edit, label_width=96))
        layout.addWidget(details)

        text = ConfigSection("Test")
        self.objective = QPlainTextEdit()
        self.objective.setMinimumHeight(60)
        self.objective.setAccessibleName("Objective")
        self.procedure = QPlainTextEdit()
        self.procedure.setMinimumHeight(60)
        self.procedure.setAccessibleName("Procedure")
        text.addWidget(FormRow("Objective", self.objective, label_width=96))
        text.addWidget(FormRow("Procedure", self.procedure, label_width=96))
        layout.addWidget(text)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self) -> None:
        path, _selected = QFileDialog.getSaveFileName(
            self, "Save workpaper", self.path_edit.text(), "Excel workbook (*.xlsx)"
        )
        if path:
            self.path_edit.setText(
                path if path.lower().endswith(".xlsx") else path + ".xlsx"
            )

    def settings(self) -> dict[str, Any]:
        values = {key: edit.text().strip() for key, edit in self.edits.items()}
        return {
            **values,
            "output_path": self.path_edit.text().strip(),
            "if_exists": self.if_exists.currentData() or "version",
            "objective": self.objective.toPlainText().strip(),
            "procedure": self.procedure.toPlainText().strip(),
        }


def build_spec(settings: dict[str, Any]):
    return node_logic.effective_spec(
        {**node_logic.DEFAULTS, **settings}, engagement_defaults(), app_version=VERSION
    )


def export_workpaper(
    main_window: Any, *, dialog_class=WorkpaperExportDialog
) -> str | None:
    """Run the whole flow for the active workflow; returns the written path or ``None``."""
    active = main_window.getCurrentNodeEditorWidget()
    if active is None:
        return None
    workflow_path = getattr(active, "filename", None) or None
    try:
        record = store_from_preferences().latest_record_dict(
            workflow_path=workflow_path
        )
    except Exception as exc:  # noqa: BLE001 - an unreadable store reads as "no run yet"
        logger.warning("Workpaper: could not read the run history: {}", exc)
        record = None
    if not record:
        QMessageBox.information(main_window, TITLE, NO_RECORD)
        return None
    dialog = dialog_class(main_window, default_output_path(workflow_path))
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    settings = dialog.settings()
    try:
        order = [int(n["node_id"]) for n in record.get("nodes") or [] if "node_id" in n]
        workflow = collect_scene_workflow(active.scene, order)
        result = write_run_workpaper(
            build_spec(settings), run_record=record, workflow=workflow
        )
    except Exception as exc:  # noqa: BLE001 - shown to the user in plain language
        logger.error("Workpaper export failed: {}", exc)
        QMessageBox.warning(main_window, "Workpaper not written", str(exc))
        return None
    folder = os.path.dirname(result.path)
    if folder:
        get_preferences().set("export/workpaper_dir", folder)
    logger.info("Workpaper written to {}", result.path)
    QMessageBox.information(main_window, TITLE, f"Workpaper written to\n{result.path}")
    return result.path
