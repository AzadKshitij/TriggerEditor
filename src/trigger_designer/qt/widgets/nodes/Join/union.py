"""Alteryx-style Union node: stack N input streams vertically (SQL UNION ALL).

Three alignment modes (matching the Alteryx Union tool):

- ``by_name`` (default): match columns by exact header (case-sensitive).
  Union of all names; rows from streams missing a column get Null.
- ``by_position``: ignore names, stack by column ordinal. Output headers
  come from the first input (extended with ``Extra_N`` when another input
  is wider); short rows are Null-padded.
- ``manual``: user-defined per-output alignment grid. Unmapped slots
  become Null.

Conflicting dtypes on a matched column/position are coerced to String
(Alteryx behaviour) with a warning on the node tooltip. The coercion is
applied explicitly at runtime; generated code relies on
``diagonal_relaxed`` supertype coercion, which was verified to produce the
same result (probes: Int64+String -> String, Null+String -> String).

Single multi-edge input socket (:class:`MultiInputNode`): any number of
edges, read in edge order (``#1`` first). Edge order persists in the file
via ``Edge.input_index``.

Undo model (see AGENTS.md): every dock section is marked
``_undo_composite`` so the Config Dock sweep skips it, and each control
commits explicitly - ``push_property_change`` for the mode,
``push_list_change`` for the mapping grid, snapshot ``storeHistory`` for
edge-order moves (edge order lives on the edges, not the content model).
"""

from typing import Any, Dict, List, Optional

import polars as pl
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.node_multi_input_node import MultiInputNode
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    register_node,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
    frame_schema,
)
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)

#: Internal mode value -> Config Dock label.
MODES: Dict[str, str] = {
    "by_name": "Auto by Name",
    "by_position": "Auto by Position",
    "manual": "Manual",
}

#: Placeholder entry in mapping combos meaning "no source -> Null".
UNMAPPED = "(none)"


def _as_lazy(frame: Any) -> Any:
    """Normalize concat inputs to LazyFrame so mixed lazy/eager works."""
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    return frame


class UnionContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Vertical stack of N ordered input frames (SQL UNION ALL)."""

    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        self.history = self.node.scene.history

        self.mode: str = "by_name"
        #: [{"output": str, "sources": [col-or-None per input]}]
        self.column_map: List[Dict[str, Any]] = []

        # Ordered inputs (read order == edge order), set by the node.
        self.input_frames: List[Any] = []
        self.input_variables: List[str] = []
        self._last_input_count: int = 0

        # pass on variables
        self.data: Optional[Any] = None
        self.variable_name: str = f"var_union_{self.id}"
        self.coercion_warnings: List[str] = []
        self.order_description: str = ""

        # Live-by-default: coalesce rapid mapping edits into one recompute.
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(300)
        self._apply_timer.timeout.connect(self._apply_debounced)
        self._applying = False

        # Dock widgets (rebuilt on every selection).
        self.mode_combo: Optional[NoWheelComboBox] = None
        self._main_layout: Optional[QVBoxLayout] = None
        self._mapping_section: Optional[ConfigSection] = None
        self._mapping_index: int = 2
        self._map_schemas: List[List[str]] = []
        self._map_rows: List[Dict[str, Any]] = []
        self._order_section: Optional[ConfigSection] = None
        self._order_row_layouts: List[QLayout] = []

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    # ------------------------------------------------------------------
    # Model helpers
    # ------------------------------------------------------------------

    def _schemas(self, frames: List[Any]) -> List[Dict[str, Any]]:
        return [dict(frame_schema(f)) for f in frames]

    def _default_column_map(self, frames: List[Any]) -> List[Dict[str, Any]]:
        """Union of names (first-seen order), sourced where present."""
        schemas = self._schemas(frames)
        outputs: List[str] = []
        for schema in schemas:
            for name in schema:
                if name not in outputs:
                    outputs.append(name)
        return [
            {"output": name, "sources": [name if name in s else None for s in schemas]}
            for name in outputs
        ]

    def _sanitize_column_map(self, count: int) -> None:
        """Fit the manual map to ``count`` inputs (pad/truncate sources)."""
        seen = set()
        clean: List[Dict[str, Any]] = []
        for row in self.column_map:
            output = str(row.get("output") or "").strip()
            if not output or output in seen:
                continue
            seen.add(output)
            sources = list(row.get("sources") or [])
            sources = (sources + [None] * count)[:count]
            clean.append({"output": output, "sources": sources})
        self.column_map = clean

    def _cast_conflicts(self, lazy_frames: List[Any], columns: List[str]) -> List[Any]:
        """Cast dtype-conflicted ``columns`` to String on every side.

        Records one warning per column for the node tooltip.
        """
        schemas = [dict(frame_schema(f)) for f in lazy_frames]
        out = list(lazy_frames)
        for col in columns:
            dtypes = {
                str(schemas[i][col]) for i in range(len(out)) if col in schemas[i]
            }
            if len(dtypes) > 1:
                self.coercion_warnings.append(
                    f"Column '{col}' has conflicting types "
                    f"({', '.join(sorted(dtypes))}); coerced to String."
                )
                for i in range(len(out)):
                    if col in schemas[i]:
                        out[i] = out[i].with_columns(
                            pl.col(col).cast(pl.String, strict=False)
                        )
        return out

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute_union(self) -> Optional[Any]:
        """Stack ``input_frames`` per ``mode``. Sets ``self.data``."""
        self.coercion_warnings = []
        frames = [f for f in self.input_frames if f is not None]
        if not frames:
            self.data = None
            return None
        if len(frames) == 1:
            self.data = frames[0]
            return self.data
        try:
            if self.mode == "by_position":
                self.data = self._concat_by_position(frames)
            elif self.mode == "manual":
                self.data = self._concat_manual(frames)
            else:
                self.data = self._concat_by_name(frames)
        except Exception as exc:
            dumpException(exc)
            self.data = None
            return None
        return self.data

    def _concat_by_name(self, frames: List[Any]) -> Any:
        lazy = [_as_lazy(f) for f in frames]
        union: List[str] = []
        for schema in self._schemas(lazy):
            for name in schema:
                if name not in union:
                    union.append(name)
        lazy = self._cast_conflicts(lazy, union)
        return pl.concat(lazy, how="diagonal_relaxed")

    def _concat_by_position(self, frames: List[Any]) -> Any:
        schemas = self._schemas(frames)
        names = [list(s) for s in schemas]
        width = max(len(n) for n in names)
        if width == 0:
            return _as_lazy(frames[0])
        headers = list(names[0]) + [
            f"Extra_{i + 1}" for i in range(len(names[0]), width)
        ]
        coerce = set()
        for pos in range(width):
            dtypes = set()
            for s in schemas:
                cols = list(s)
                if pos < len(cols):
                    dtypes.add(str(s[cols[pos]]))
            if len(dtypes) > 1:
                coerce.add(pos)
                self.coercion_warnings.append(
                    f"Position {pos + 1} has conflicting types "
                    f"({', '.join(sorted(dtypes))}); coerced to String."
                )
        staged = []
        for f, cols in zip(frames, names):
            exprs = []
            for pos in range(width):
                target = f"_u{pos}"
                if pos < len(cols):
                    expr = pl.col(cols[pos])
                    if pos in coerce:
                        expr = expr.cast(pl.String, strict=False)
                    exprs.append(expr.alias(target))
                else:
                    exprs.append(pl.lit(None).alias(target))
            staged.append(_as_lazy(f).select(exprs))
        return pl.concat(staged, how="diagonal_relaxed").rename(
            {f"_u{i}": headers[i] for i in range(width)}
        )

    def _concat_manual(self, frames: List[Any]) -> Any:
        count = len(frames)
        if not self.column_map:
            self.column_map = self._default_column_map(frames)
        self._sanitize_column_map(count)
        rows = [r for r in self.column_map if str(r.get("output") or "").strip()]
        if not rows:
            rows = self._default_column_map(frames)
            self.column_map = [dict(r) for r in rows]
        schemas = self._schemas(frames)
        coerce = set()
        for row in rows:
            dtypes = {
                str(schemas[i][src])
                for i, src in enumerate(row["sources"])
                if src and src in schemas[i]
            }
            if len(dtypes) > 1:
                coerce.add(row["output"])
                self.coercion_warnings.append(
                    f"Column '{row['output']}' has conflicting types "
                    f"({', '.join(sorted(dtypes))}); coerced to String."
                )
        staged = []
        for i, f in enumerate(frames):
            exprs = []
            for row in rows:
                out = row["output"]
                src = row["sources"][i]
                if src and src in schemas[i]:
                    expr = pl.col(src)
                    if out in coerce:
                        expr = expr.cast(pl.String, strict=False)
                    exprs.append(expr.alias(out))
                else:
                    exprs.append(pl.lit(None).alias(out))
            staged.append(_as_lazy(f).select(exprs))
        return pl.concat(staged, how="diagonal_relaxed")

    # ------------------------------------------------------------------
    # Config Dock
    # ------------------------------------------------------------------

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        if not self.input_frames:
            dock_layout.addWidget(EmptyStateLabel("Connect at least one input"))
            return dock_layout

        self.mode_combo = None
        self._mapping_section = None
        self._map_rows = []
        self._order_section = None
        self._order_row_layouts = []

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(2)
        self._main_layout = main_layout

        self._build_mode_section(main_layout)
        self._build_order_section(main_layout)
        if self.mode == "manual":
            self._sanitize_column_map(len(self.input_frames))
            self._mapping_index = main_layout.count()
            self._build_mapping_section(main_layout)

        main_layout.addStretch()
        dock_layout.addLayout(main_layout)
        # NOTE: no recursively_find_widgets here. Every section below is
        # marked _undo_composite and commits explicitly, so the Config Dock
        # sweep must skip these children - binding them too would record
        # every edit twice.
        return dock_layout

    @staticmethod
    def _mark_composite(widget: QWidget) -> None:
        widget._undo_composite = True  # type: ignore[attr-defined]

    def _build_mode_section(self, main_layout: QVBoxLayout) -> None:
        section = ConfigSection(
            "Union Mode", info="How columns from the inputs are aligned."
        )
        self._mark_composite(section)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Mode"))
        self.mode_combo = NoWheelComboBox()
        # Populate before connecting: no signal may fire during build.
        self.mode_combo.addItems(
            [MODES[m] for m in ("by_name", "by_position", "manual")]
        )
        self.mode_combo.setMinimumHeight(30)
        self.mode_combo.setToolTip(
            "Auto by Name: match exact column headers.\n"
            "Auto by Position: stack by column order, ignore names.\n"
            "Manual: align columns yourself in the grid below."
        )
        self.mode_combo.setCurrentText(MODES.get(self.mode, MODES["by_name"]))
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        row.addWidget(self.mode_combo, 1)
        section.addLayout(row)
        main_layout.addWidget(section)

    def _build_order_section(self, main_layout: QVBoxLayout) -> None:
        section = ConfigSection(
            "Input Order",
            info="Rows stack #1 first. Reorder with Up/Down or reconnect edges.",
        )
        self._mark_composite(section)
        self._order_section = section
        self._refresh_order_rows()
        main_layout.addWidget(section)

    def _ordered_edge_labels(self) -> List[str]:
        try:
            edges = self.node.getOrderedEdges()
        except (AttributeError, RuntimeError):
            return []
        labels = []
        for pos, edge in enumerate(edges):
            try:
                other = edge.getOtherSocket(self.node.inputs[0])
                if other is not None and getattr(other, "node", None) is not None:
                    labels.append(f"#{pos + 1} {other.node.title} [out {other.index}]")
                else:
                    labels.append(f"#{pos + 1} ?")
            except (AttributeError, RuntimeError):
                labels.append(f"#{pos + 1} ?")
        return labels

    def _refresh_order_rows(self) -> None:
        section = self._order_section
        if section is None:
            return
        for layout in self._order_row_layouts:
            self._delete_layout(layout)
        self._order_row_layouts = []
        try:
            edges = self.node.getOrderedEdges()
        except (AttributeError, RuntimeError):
            edges = []
        labels = self._ordered_edge_labels()
        for pos, (edge, label) in enumerate(zip(edges, labels)):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name = QLabel(label)
            name.setMinimumHeight(30)
            row.addWidget(name, 1)
            up_btn = IconButton.themed(
                f"Move input {pos + 1} earlier",
                rsm_icon=None,
                qss_fallback=":/qss_icons/dark/rc/arrow_up.png",
                theme_fallback="go-up",
            )
            down_btn = IconButton.themed(
                f"Move input {pos + 1} later",
                rsm_icon=None,
                qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
                theme_fallback="go-down",
            )
            up_btn.clicked.connect(
                lambda _checked=False, e=edge, p=pos: self._move_input(e, p - 1)
            )
            down_btn.clicked.connect(
                lambda _checked=False, e=edge, p=pos: self._move_input(e, p + 1)
            )
            row.addWidget(up_btn)
            row.addWidget(down_btn)
            section.addLayout(row)
            self._order_row_layouts.append(row)

    def _build_mapping_section(self, main_layout: QVBoxLayout) -> None:
        section = ConfigSection(
            "Column Mapping",
            info="Align each input's column to an output. Blank = Null.",
        )
        self._mark_composite(section)
        self._mapping_section = section
        self._map_schemas = [list(s) for s in self._schemas(self.input_frames)]
        self._map_rows = []

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        output_head = QLabel("Output")
        output_head.setObjectName("ConfigSectionInfo")
        header.addWidget(output_head, 1)
        for i, var in enumerate(self.input_variables):
            head = QLabel(var or f"Input {i + 1}")
            head.setObjectName("ConfigSectionInfo")
            header.addWidget(head, 1)
        head_filler = QLabel("")
        head_filler.setFixedWidth(30)
        header.addWidget(head_filler)
        section.addLayout(header)

        for row in self.column_map:
            self._add_mapping_row(section, row)
        add_btn = IconButton.themed(
            "Add output column",
            rsm_icon=self.node.rsm.get("icon_add"),
        )
        add_btn.clicked.connect(self._on_add_mapping_row)
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        section.addLayout(add_row)
        main_layout.addWidget(section)

    def _refresh_mapping_section(self) -> None:
        """Rebuild the mapping grid from the model (restore-time path)."""
        if self._main_layout is None or self._mapping_section is None:
            return
        self._delete_section(self._main_layout, self._mapping_section)
        self._mapping_section = None
        self._map_rows = []
        if self.mode == "manual":
            self._sanitize_column_map(len(self.input_frames))
            self._build_mapping_section_at(self._mapping_index)

    def _build_mapping_section_at(self, index: int) -> None:
        section = ConfigSection(
            "Column Mapping",
            info="Align each input's column to an output. Blank = Null.",
        )
        self._mark_composite(section)
        self._mapping_section = section
        self._map_schemas = [list(s) for s in self._schemas(self.input_frames)]
        self._map_rows = []
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        output_head = QLabel("Output")
        output_head.setObjectName("ConfigSectionInfo")
        header.addWidget(output_head, 1)
        for i, var in enumerate(self.input_variables):
            head = QLabel(var or f"Input {i + 1}")
            head.setObjectName("ConfigSectionInfo")
            header.addWidget(head, 1)
        head_filler = QLabel("")
        head_filler.setFixedWidth(30)
        header.addWidget(head_filler)
        section.addLayout(header)
        for row in self.column_map:
            self._add_mapping_row(section, row)
        add_btn = IconButton.themed(
            "Add output column",
            rsm_icon=self.node.rsm.get("icon_add"),
        )
        add_btn.clicked.connect(self._on_add_mapping_row)
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        section.addLayout(add_row)
        if self._main_layout is not None:
            self._main_layout.insertWidget(index, section)

    def _add_mapping_row(self, section: ConfigSection, row: Dict[str, Any]) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        output_edit = QLineEdit()
        output_edit.setPlaceholderText("Output column")
        output_edit.setMinimumHeight(30)
        output_edit.setText(str(row.get("output") or ""))
        output_edit.textChanged.connect(self._schedule_mapping_apply)
        layout.addWidget(output_edit, 1)
        combos: List[NoWheelComboBox] = []
        sources = list(row.get("sources") or [])
        for i, columns in enumerate(self._map_schemas):
            combo = NoWheelComboBox()
            combo.addItem(UNMAPPED)
            combo.addItems(columns)
            current = sources[i] if i < len(sources) else None
            if current and combo.findText(current) >= 0:
                combo.setCurrentText(current)
            combo.setMinimumHeight(30)
            combo.setToolTip(
                f"Column from {self.input_variables[i] if i < len(self.input_variables) else f'input {i + 1}'}"
            )
            combo.currentTextChanged.connect(self._schedule_mapping_apply)
            combos.append(combo)
            layout.addWidget(combo, 1)
        remove_btn = IconButton.themed(
            "Remove output column",
            rsm_icon=self.node.rsm.get("icon_remove"),
        )
        entry = {"layout": layout, "output": output_edit, "combos": combos}
        remove_btn.clicked.connect(
            lambda _checked=False, e=entry: self._on_remove_mapping_row(e)
        )
        layout.addWidget(remove_btn)
        section.addLayout(layout)
        self._map_rows.append(entry)

    # ------------------------------------------------------------------
    # Dock slots (all guarded: model->widget writes must never re-record)
    # ------------------------------------------------------------------

    def _guarded(self) -> bool:
        return self.history.is_restoring_history or is_syncing(self)

    def _on_mode_changed(self, label: str) -> None:
        if self._guarded():
            return
        lookup = {v: k for k, v in MODES.items()}
        new_mode = lookup.get(label, "by_name")
        if new_mode == self.mode:
            return
        old_mode = self.mode
        self.mode = new_mode
        if new_mode == "manual" and not self.column_map:
            self.column_map = self._default_column_map(self.input_frames)
        # The command re-projects the widgets and re-evaluates via
        # sync_from_model; nothing else to do here.
        self.push_property_change(
            ("mode",), old_mode, new_mode, "Union Mode Changed", rebuild=True
        )

    def _move_input(self, edge: Any, position: int) -> None:
        if self._guarded():
            return
        try:
            changed = self.node.moveEdgeTo(edge, position)
        except (AttributeError, RuntimeError):
            return
        if not changed:
            return
        # Edge order lives on the edges: refresh the rows, re-evaluate in
        # the new order, then snapshot the scene for undo.
        self.sync_from_model(rebuild=True)
        self.history.storeHistory("Input Order Changed", setModified=True)

    def _schedule_mapping_apply(self) -> None:
        if not self._applying and not self._guarded():
            self._apply_timer.start()

    def _apply_debounced(self) -> None:
        if self._applying or self._guarded():
            return
        self._applying = True
        try:
            self._commit_mapping()
        finally:
            self._applying = False

    def _read_mapping(self) -> List[Dict[str, Any]]:
        count = len(self.input_frames)
        rows = []
        for entry in self._map_rows:
            try:
                output = entry["output"].text().strip()
            except RuntimeError:
                continue
            if not output:
                continue
            sources = []
            for combo in entry["combos"]:
                try:
                    text = combo.currentText()
                except RuntimeError:
                    text = UNMAPPED
                sources.append(None if text == UNMAPPED else text)
            sources = (sources + [None] * count)[:count]
            rows.append({"output": output, "sources": sources})
        return rows

    def _commit_mapping(self) -> None:
        old = [dict(r, sources=list(r["sources"])) for r in self.column_map]
        new = self._read_mapping()
        if old == new:
            return
        self.column_map = new
        self.push_list_change(("column_map",), old, new, "Union Columns Mapped")

    def _unique_output_name(self, base: str = "New_Column") -> str:
        taken = {str(r.get("output") or "") for r in self.column_map}
        name, i = base, 1
        while name in taken:
            i += 1
            name = f"{base}_{i}"
        return name

    def _on_add_mapping_row(self, _checked: bool = False) -> None:
        if self._guarded():
            return
        old = [dict(r, sources=list(r["sources"])) for r in self.column_map]
        count = len(self.input_frames)
        new = old + [{"output": self._unique_output_name(), "sources": [None] * count}]
        self.column_map = new
        self.push_list_change(("column_map",), old, new, "Union Column Added")

    def _on_remove_mapping_row(self, entry: Dict[str, Any]) -> None:
        if self._guarded() or entry not in self._map_rows:
            return
        old = [dict(r, sources=list(r["sources"])) for r in self.column_map]
        self._map_rows.remove(entry)
        self._delete_layout(entry["layout"])
        new = self._read_mapping()
        self.column_map = new
        self.push_list_change(("column_map",), old, new, "Union Column Removed")

    @staticmethod
    def _delete_layout(layout: Optional[QLayout]) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            elif item.layout() is not None:
                UnionContent._delete_layout(item.layout())
        layout.deleteLater()

    def _delete_section(self, parent: QVBoxLayout, section: ConfigSection) -> None:
        for i in range(parent.count()):
            if parent.itemAt(i).widget() is section:
                parent.takeAt(i)
                break
        section.deleteLater()

    def _report_warnings(self) -> None:
        try:
            self.node.grNode.setToolTip("\n".join(self.coercion_warnings))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Undo projection
    # ------------------------------------------------------------------

    def _sync_widgets_from_model(self) -> None:
        if self.mode_combo is not None:
            try:
                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentText(MODES.get(self.mode, MODES["by_name"]))
            except RuntimeError:
                self.mode_combo = None
            finally:
                try:
                    if self.mode_combo is not None:
                        self.mode_combo.blockSignals(False)
                except RuntimeError:
                    self.mode_combo = None
        if self._mapping_section is not None:
            try:
                self._mapping_section.setVisible(self.mode == "manual")
            except RuntimeError:
                self._mapping_section = None

    def _rebuild_widgets(self) -> None:
        try:
            self._refresh_order_rows()
            self._refresh_mapping_section()
        except RuntimeError:
            self._order_section = None
            self._mapping_section = None
            self._map_rows = []

    # ------------------------------------------------------------------
    # Codegen / persistence
    # ------------------------------------------------------------------

    def get_code(self) -> str:
        if not self.input_variables:
            return f"import polars as pl\n{self.variable_name} = pl.DataFrame()\n"
        if self.mode == "by_position":
            return self._position_code()
        if self.mode == "manual":
            return self._manual_code()
        lines = ["import polars as pl"]
        lines.append(f"_union_inputs_{self.id} = [{', '.join(self.input_variables)}]")
        lines.append(
            f"{self.variable_name} = pl.concat("
            f"[(f.lazy() if isinstance(f, pl.DataFrame) else f) "
            f"for f in _union_inputs_{self.id}], how='diagonal_relaxed')"
        )
        lines.append(f"del _union_inputs_{self.id}")
        return "\n".join(lines) + "\n"

    def _position_code(self) -> str:
        schemas = [list(frame_schema(f)) for f in self.input_frames]
        width = max((len(n) for n in [s for s in schemas]), default=0)
        headers = (schemas[0] if schemas else []) + [
            f"Extra_{i + 1}" for i in range(len(schemas[0]) if schemas else 0, width)
        ]
        rename = "{" + ", ".join(f"'_u{i}': {h!r}" for i, h in enumerate(headers)) + "}"
        lines = ["import polars as pl", f"{self.variable_name} = pl.concat(["]
        for var, cols in zip(self.input_variables, schemas):
            parts = []
            for pos in range(width):
                if pos < len(cols):
                    parts.append(f"pl.col({cols[pos]!r}).alias('_u{pos}')")
                else:
                    parts.append(f"pl.lit(None).alias('_u{pos}')")
            lines.append(f"    {var}.select([{', '.join(parts)}]),")
        lines.append(f"], how='diagonal_relaxed').rename({rename})")
        return "\n".join(lines) + "\n"

    def _manual_code(self) -> str:
        # Runtime dtype coercion is handled by diagonal_relaxed (verified
        # equivalent), so codegen only needs the rename/select structure.
        lines = ["import polars as pl", f"{self.variable_name} = pl.concat(["]
        for i, var in enumerate(self.input_variables):
            parts = []
            for row in self.column_map:
                out = row.get("output") or ""
                sources = row.get("sources") or []
                src = sources[i] if i < len(sources) else None
                if out and src:
                    parts.append(f"pl.col({src!r}).alias({out!r})")
                elif out:
                    parts.append(f"pl.lit(None).alias({out!r})")
            lines.append(f"    {var}.select([{', '.join(parts)}]),")
        lines.append("], how='diagonal_relaxed')")
        return "\n".join(lines) + "\n"

    def serialize(self) -> Dict[str, Any]:
        res = super().serialize()
        res["mode"] = self.mode
        res["column_map"] = self.column_map
        return res

    def deserialize(self, data: Dict[str, Any], hashmap: Dict[str, Any] = {}) -> bool:
        res = super().deserialize(data, hashmap)
        try:
            mode = data.get("mode", "by_name")
            self.mode = mode if mode in MODES else "by_name"
            self.column_map = data.get("column_map", []) or []
            return True and res
        except Exception as exc:
            dumpException(exc)
        return res


@register_node(JoinNodes.UNION, NodeTypes.JOIN)
class TriggerNode_Union(MultiInputNode, TriggerNode):
    """Stack any number of input streams vertically (SQL UNION ALL)."""

    icon = "node_union"
    node_code = JoinNodes.UNION
    node_type = NodeTypes.JOIN
    node_title = "Union"
    content_label_objname = "trigger_node_union"
    style = {}

    def __init__(self, scene) -> None:
        # MultiInputNode defines no __init__: this runs TriggerNode's,
        # while initSettings/initSockets resolve multi-input first.
        super().__init__(scene, inputs=[1], outputs=[3])

    def initInnerClasses(self) -> None:
        self.content: UnionContent = UnionContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List[Dict[str, Any]] = []

    def evalImplementation(self) -> Optional[List[Dict[str, Any]]]:
        try:
            ordered = self.getOrderedEdges()
        except (AttributeError, RuntimeError):
            ordered = []
        if not ordered:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Connect at least one input")
            return None

        frames: List[Any] = []
        variables: List[str] = []
        socket = self.inputs[0]
        for edge in ordered:
            try:
                other = edge.getOtherSocket(socket)
            except (AttributeError, RuntimeError):
                continue
            if other is None or getattr(other, "node", None) is None:
                continue
            try:
                val = other.node.eval()
            except Exception:
                continue
            if val is None:
                continue
            entry: Optional[Dict[str, Any]] = None
            if isinstance(val, list):
                if 0 <= other.index < len(val) and isinstance(val[other.index], dict):
                    entry = val[other.index]
            elif isinstance(val, dict):
                entry = val
            if not entry or entry.get("data") is None:
                continue
            frames.append(entry.get("data"))
            variables.append(entry.get("variable_name", ""))

        if not frames:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Upstream nodes produced no output")
            return None

        self.content.input_frames = frames
        self.content.input_variables = variables
        try:
            self.content.order_description = self.describeInputOrder()
        except (AttributeError, RuntimeError):
            self.content.order_description = ""

        # New edge while the dock is open: rebuild the mapping grid so the
        # new input's columns appear. Typing commits never change the count,
        # so focused editors are never torn down by this.
        if len(frames) != self.content._last_input_count:
            self.content._last_input_count = len(frames)
            self.content._sanitize_column_map(len(frames))
            self.content.sync_from_model(rebuild=True, evaluate=False)

        if self.content.execute_union() is None:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Union failed")
            return None

        # markDirty(False)/markInvalid(False)/evalChildren() all wait until
        # self.value actually holds the new result: a child pulled earlier
        # (e.g. by an evalChildren() call above, or by a sibling reentering
        # this node mid-computation) would otherwise see this node as
        # "clean" while self.value is still the previous, stale result.
        self.param = [
            {
                "data": self.content.data,
                "variable_name": self.content.variable_name,
            }
        ]
        self.value = self.param
        self.markInvalid(False)
        self.markDirty(False)
        if self.content.coercion_warnings:
            self.grNode.setToolTip("\n".join(self.content.coercion_warnings))
        else:
            self.grNode.setToolTip("")
        self.evalChildren()
        self._refresh_selected_node_config()
        return self.param

    def get_code(self):
        return self.content.get_code()
