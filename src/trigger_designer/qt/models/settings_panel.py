import os

import orjson as json
from loguru import logger
from qtpy.QtCore import QSettings
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.node_editor_colors import (
    DEFAULT_EDGE_COLORS,
    DEFAULT_SOCKET_COLORS,
    load_node_editor_colors,
    save_node_editor_colors,
)
from trigger_designer.qt.resource_manager import ResourceManager


class ColorPickerButton(QPushButton):
    """A small swatch button that opens a ``QColorDialog`` on click."""

    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(60, 26)
        self._color = QColor(color)
        self.clicked.connect(self._pick_color)
        self._update_swatch()

    def _update_swatch(self) -> None:
        self.setText(self._color.name())
        self.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"color: {'#000000' if self._color.lightness() > 128 else '#ffffff'};"
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(
            self._color,
            self,
            "Choose color",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self.color = color

    @property
    def color(self) -> QColor:
        return QColor(self._color)

    @color.setter
    def color(self, value) -> None:
        self._color = QColor(value)
        self._update_swatch()


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.rsm: ResourceManager = ResourceManager()
        self.settings = QSettings("Blue Octa", "Trigger Designer")
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Create tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout()
        appearance_tab.setLayout(appearance_layout)

        # Theme settings
        theme_group = QGroupBox("Theme")
        theme_layout = QFormLayout()

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.settings.value("theme", "dark"))
        theme_layout.addRow("Theme:", self.theme_combo)

        theme_group.setLayout(theme_layout)
        appearance_layout.addWidget(theme_group)

        # Editor settings
        editor_group = QGroupBox("Editor")
        editor_layout = QFormLayout()

        self.grid_size = QSpinBox()
        self.grid_size.setRange(10, 100)
        self.grid_size.setValue(self.settings.value("grid_size", 20))
        editor_layout.addRow("Grid Size:", self.grid_size)

        self.show_grid = QCheckBox()
        self.show_grid.setChecked(self.settings.value("show_grid", True))
        editor_layout.addRow("Show Grid:", self.show_grid)

        editor_group.setLayout(editor_layout)
        appearance_layout.addWidget(editor_group)

        tabs.addTab(appearance_tab, "Appearance")

        # Node Editor tab (edge / socket colors)
        node_editor_tab = QWidget()
        node_editor_layout = QVBoxLayout()
        node_editor_tab.setLayout(node_editor_layout)

        saved_colors = load_node_editor_colors(self.settings)

        edge_group = QGroupBox("Edge Colors")
        edge_layout = QFormLayout()
        self.edge_color_buttons: dict[str, ColorPickerButton] = {
            "default": ColorPickerButton(saved_colors["edges"]["default"]),
            "selected": ColorPickerButton(saved_colors["edges"]["selected"]),
            "hovered": ColorPickerButton(saved_colors["edges"]["hovered"]),
            "dragging": ColorPickerButton(saved_colors["edges"]["dragging"]),
        }
        edge_layout.addRow("Default:", self.edge_color_buttons["default"])
        edge_layout.addRow("Selected:", self.edge_color_buttons["selected"])
        edge_layout.addRow("Hover / Highlight:", self.edge_color_buttons["hovered"])
        edge_layout.addRow("Dragging:", self.edge_color_buttons["dragging"])
        edge_group.setLayout(edge_layout)
        node_editor_layout.addWidget(edge_group)

        socket_group = QGroupBox("Socket Colors")
        socket_layout = QFormLayout()
        self.socket_color_buttons: dict[str, ColorPickerButton] = {
            "outline": ColorPickerButton(saved_colors["sockets"]["outline"]),
            "highlight": ColorPickerButton(saved_colors["sockets"]["highlight"]),
        }
        socket_layout.addRow("Outline:", self.socket_color_buttons["outline"])
        socket_layout.addRow("Highlight:", self.socket_color_buttons["highlight"])
        socket_group.setLayout(socket_layout)
        node_editor_layout.addWidget(socket_group)

        reset_colors_btn = QPushButton("Reset to Defaults")
        reset_colors_btn.clicked.connect(self._reset_node_editor_colors)
        node_editor_layout.addWidget(reset_colors_btn)

        node_editor_layout.addStretch()
        tabs.addTab(node_editor_tab, "Node Editor")

        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _reset_node_editor_colors(self) -> None:
        for key, button in self.edge_color_buttons.items():
            button.color = DEFAULT_EDGE_COLORS[key]
        for key, button in self.socket_color_buttons.items():
            button.color = DEFAULT_SOCKET_COLORS[key]

    def load_settings(self):

        return {}

    def save_settings(self) -> None:
        settings = {
            "theme": self.theme_combo.currentText(),
            "grid_size": self.grid_size.value(),
            "show_grid": self.show_grid.isChecked(),
        }

        node_editor_colors = {
            "edges": {
                key: button.color.name(QColor.NameFormat.HexArgb)
                for key, button in self.edge_color_buttons.items()
            },
            "sockets": {
                key: button.color.name(QColor.NameFormat.HexArgb)
                for key, button in self.socket_color_buttons.items()
            },
        }
        save_node_editor_colors(node_editor_colors, self.settings)

        # settings_file = os.path.join(os.path.dirname(
        #     __file__), "../resources/settings.json")
        import sys
        from pathlib import Path

        settings_file = self.rsm._res_folder / "resources/qt/settings.json"
        if getattr(sys, "frozen", False):
            # ponytail: bundle is read-only when installed; persist to user scope
            appdata = os.getenv("APPDATA")
            base = (
                Path(appdata) / "Trigger Designer"
                if appdata
                else Path.home() / ".trigger_designer"
            )
            settings_file = base / "settings.json"

        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        settings_json = json.dumps(settings, option=json.OPT_INDENT_2)

        with open(settings_file, "w") as f:
            f.write(settings_json.decode())

        qsettings = QSettings("Blue Octa", "Trigger Designer")

        logger.info(settings)
        logger.debug(qsettings.allKeys())

        theme = settings.get("theme", "dark")
        print("🐍 File: models/settings_panel.py:106 | save_settings ~ theme", theme)
        grid_size = settings.get("grid_size", 20)
        show_grid = settings.get("show_grid", True)

        qsettings.setValue("theme", theme)
        print("🐍 File: models/settings_panel.py:111 | save_settings ~ theme", theme)

        style_sheet = self.rsm.load_theme(theme)
        print("🐍 File: models/settings_panel.py:114 | save_settings ~ theme", theme)

        QApplication.instance().setStyleSheet(style_sheet)

        self.accept()
