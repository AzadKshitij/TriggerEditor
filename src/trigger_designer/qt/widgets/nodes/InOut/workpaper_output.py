"""Workpaper Output node: Qt wrapper only; the writer lives in core/workpaper.

Three inputs (Exceptions required; Population and Summary optional) and no
outputs. Nothing is written while editing: the workbook is written by Run, from
the generated code (``run_workpaper``).
"""

from __future__ import annotations

import os
import threading

from loguru import logger
from qtpy.QtWidgets import QFileDialog, QVBoxLayout

from trigger_designer.core.constants import VERSION
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    register_node,
)
from trigger_designer.core.workpaper import node_logic
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
)
from trigger_designer.qt.helpers.workflow_snapshot import (
    collect_sources,
    collect_workflow,
)
from trigger_designer.qt.node_base import TriggerGraphicsNode, TriggerNode
from trigger_designer.qt.preferences import get_preferences
from trigger_designer.qt.widgets.common import EmptyStateLabel, FormRow, IconButton

NODE_DEFAULTS = node_logic.DEFAULTS

#: Settings whose row carries a browse button.
_BROWSE = {
    "output_path": "Browse for save location",
    "logo_path": "Browse for logo image",
}

#: Text settings that inherit from Engagement preferences when left empty.
_INHERITED = {
    "client": "engagement/client_name",
    "engagement": "engagement/engagement_name",
    "period": "engagement/period",
    "preparer": "engagement/preparer",
    "logo_path": "engagement/logo_path",
}


def _text(key: str, label: str, **kw) -> Field:
    return Field(key, label, "text", **kw)


def engagement_from_preferences() -> dict[str, str]:
    prefs = get_preferences()
    return {
        "client_name": str(prefs.get("engagement/client_name", "") or ""),
        "engagement_name": str(prefs.get("engagement/engagement_name", "") or ""),
        "period": str(prefs.get("engagement/period", "") or ""),
        "preparer": str(prefs.get("engagement/preparer", "") or ""),
        "logo_path": str(prefs.get("engagement/logo_path", "") or ""),
    }


class WorkpaperOutputContent(ShapingContent):
    SETTINGS = NODE_DEFAULTS
    MODULE = "trigger_designer.core.workpaper.node_logic"
    OUTPUT_KINDS = ()
    INPUTS = 3
    OPTIONAL_INPUTS = frozenset({1, 2})
    HISTORY = "Workpaper"
    SUMMARY = "write the audit workpaper"
    FORM = (
        FormSection(
            "File",
            (
                _text("output_path", "File", placeholder="Enter file path (.xlsx)"),
                Field(
                    "if_exists",
                    "If it exists",
                    "combo",
                    options=node_logic.IF_EXISTS_LABELS,
                    tip="New version keeps a workpaper you already annotated",
                ),
            ),
        ),
        FormSection(
            "Engagement",
            (
                _text("workpaper_ref", "Reference", placeholder="e.g. C.3.1"),
                _text("client", "Client"),
                _text("engagement", "Engagement"),
                _text("period", "Period"),
                _text("preparer", "Prepared by"),
                _text("prepared_date", "Prepared on", placeholder="today (YYYY-MM-DD)"),
                _text("logo_path", "Logo", placeholder="PNG or JPG"),
            ),
            collapsible=True,
        ),
        FormSection(
            "Test",
            (
                _text("test_name", "Test name"),
                Field("objective", "Objective", "textarea"),
                Field("procedure", "Procedure", "textarea"),
                Field("criteria", "Criteria", "textarea"),
            ),
        ),
        FormSection(
            "Values",
            (
                Field(
                    "amount_column",
                    "Amount column",
                    "column",
                    blank=True,
                    filter="",
                    tip="Column summed for the value statistics",
                ),
                Field("value_decimals", "Decimals", "int", minimum=0, maximum=6),
            ),
        ),
        FormSection(
            "Sheets",
            (
                Field(
                    "row_limit",
                    "Row limit",
                    "int",
                    minimum=1,
                    maximum=1_048_574,
                    hint="Large workpapers may exceed the 30 second per-node limit; lower the row limit.",
                ),
                _text("exceptions_sheet_name", "Exceptions sheet"),
                Field("include_run_log", "Include run log", "check"),
                Field("include_workflow", "Include workflow", "check"),
            ),
        ),
        FormSection(
            "Sources",
            (
                Field(
                    "source_files",
                    "Extra source files",
                    "textarea",
                    placeholder="One path per line",
                    tip="Files read outside the workflow; they are hashed when the workpaper is written",
                ),
            ),
            collapsible=True,
            collapsed=True,
        ),
    )

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        #: Filled on the GUI thread by ``before_run`` (``get_code`` runs on a worker).
        self._engagement: dict[str, str] | None = None
        self._workflow: list[dict] | None = None
        self._sources: list[dict] | None = None

    # ---- snapshots taken on the GUI thread --------------------------------
    def before_run(self) -> None:
        """Called by Run Workflow on the GUI thread, before the worker starts."""
        try:
            self._engagement = engagement_from_preferences()
            self._workflow = collect_workflow(self.node)
            self._sources = collect_sources(self.node)
        except Exception as exc:  # noqa: BLE001 - keep the previous snapshot
            logger.warning("Workpaper Output: could not snapshot the workflow: {}", exc)

    def effective_spec(self):
        engagement = self._engagement
        if engagement is None and threading.current_thread() is threading.main_thread():
            engagement = engagement_from_preferences()
        return node_logic.effective_spec(self.settings, engagement, app_version=VERSION)

    def get_code(self) -> str:
        if (
            self._workflow is None
            and threading.current_thread() is threading.main_thread()
        ):
            self.before_run()
        return node_logic.build_code(
            self.effective_spec(),
            self.input_vars,
            workflow=self._workflow,
            sources=self._sources,
        )

    # ---- dock ---------------------------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.frames[0] is None:
            dock_layout.addWidget(EmptyStateLabel("Connect the Exceptions input"))
            return
        super().create_layout(dock_layout)
        prefs = engagement_from_preferences()
        mapping = {
            "client": prefs["client_name"],
            "engagement": prefs["engagement_name"],
            "period": prefs["period"],
            "preparer": prefs["preparer"],
            "logo_path": prefs["logo_path"],
        }
        for key, value in mapping.items():
            widget = self._widgets.get(key)
            if widget is not None and value and hasattr(widget, "setPlaceholderText"):
                widget.setPlaceholderText(value)
        spin = self._widgets.get("row_limit")
        if spin is not None:
            spin.setSingleStep(10_000)

    def _build_row(self, spec: Field):
        if spec.key not in _BROWSE:
            return super()._build_row(spec)

        def commit(value, spec=spec) -> None:
            self.set_setting(
                spec.key,
                value,
                f"{self.HISTORY} {spec.label} Changed",
                self._burst_key(spec),
            )

        widget = self._make_widget(spec, self.settings.get(spec.key), commit)
        self._widgets[spec.key] = widget
        button = IconButton.themed(
            _BROWSE[spec.key], rsm_icon=self.node.rsm.get("icon_save")
        )
        button.clicked.connect(lambda _checked=False, key=spec.key: self.browse(key))
        return FormRow(spec.label, widget, label_width=96, action=button)

    def browse(self, key: str) -> str:
        """Ask for a path and store it; returns the chosen path (``""`` if cancelled)."""
        current = str(self.settings.get(key) or "")
        if key == "output_path":
            start = current or str(
                get_preferences().get("export/workpaper_dir", "") or ""
            )
            path, _selected = QFileDialog.getSaveFileName(
                self.parent(), "Save workpaper", start, "Excel workbook (*.xlsx)"
            )
            if path and not path.lower().endswith(".xlsx"):
                path += ".xlsx"
            if path:
                get_preferences().set("export/workpaper_dir", os.path.dirname(path))
        else:
            path, _selected = QFileDialog.getOpenFileName(
                self.parent(), "Logo image", current, "Images (*.png *.jpg *.jpeg)"
            )
        if not path:
            return ""
        widget = self._widgets.get(key)
        if widget is not None:
            widget.setText(path)
        else:
            self.set_setting(key, path, f"{self.HISTORY} {key} Changed")
        return path

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        path = str(self.settings.get("output_path") or "")
        mode = dict(node_logic.IF_EXISTS_LABELS).get(
            str(self.settings.get("if_exists")), "New version"
        )
        chips = [
            ("xlsx", "accent"),
            (f"{int(self.settings.get('row_limit') or 0):,} row limit", ""),
            (mode.lower(), ""),
        ]
        return chips, os.path.basename(path)

    def validate_loaded_state(self) -> list[str]:
        if not str(self.settings.get("output_path") or ""):
            return ["Workpaper Output has no output file; choose one before running."]
        return []


@register_node(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)
class TriggerNode_WorkpaperOutput(TriggerNode):
    icon = "node_file_output"
    node_code = IONodes.WORKPAPER_OUTPUT
    node_title = "Workpaper Output"
    node_type = NodeTypes.IO
    content_label_objname = "trigger_node_workpaper_output"
    style = {}  # noqa: RUF012 - shared empty node style
    #: Population and Summary may stay unconnected; Exceptions may not.
    optional_inputs = frozenset({1, 2})

    def __init__(self, scene) -> None:
        super().__init__(
            scene, inputs=[1, 1, 1], outputs=[], input_text=["E", "P", "S"]
        )

    def initInnerClasses(self) -> None:
        self.content = WorkpaperOutputContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def _fail(self, message: str):
        self.markDirty(True)
        self.markInvalid(True)
        self.grNode.setToolTip(message)

    def processInputs(self, input_values):
        content = self.content
        first = None
        for index, role in enumerate(node_logic.ROLES):
            upstream = socket = None
            try:
                upstream, socket = self.getInputWithSocket(index)
            except Exception:  # noqa: BLE001, S110 - unconnected input
                pass
            entry = None
            if upstream is not None and socket is not None and input_values:
                row = input_values[index] if index < len(input_values) else None
                if row and socket.index < len(row):
                    entry = row[socket.index]
            if entry is None or entry.get("data") is None:
                content.frames[index] = None
                content.input_vars[index] = ""
                if index == 0:
                    return self._fail("Connect the Exceptions input")
                if upstream is not None:  # connected but failed: never ignored
                    return self._fail(f"{role} input has no data")
                continue
            content.frames[index] = entry["data"]
            content.input_vars[index] = entry.get("variable_name") or ""
            if index == 0:
                first = entry
        tip = ""
        amount = str(content.settings.get("amount_column") or "")
        if amount and amount not in content.schema(0):
            tip = f"The amount column '{amount}' is not in the Exceptions input"
        self.param = []
        self.markDirty(False)
        self.markInvalid(False)
        self.grNode.setToolTip(tip)
        return first

    def get_code(self) -> str:
        return self.content.get_code()
