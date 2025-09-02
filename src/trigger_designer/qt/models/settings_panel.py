from loguru import logger
from qtpy.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
                            QPushButton, QLabel, QComboBox, QSpinBox,
                            QCheckBox, QGroupBox, QFormLayout, QWidget, QApplication)
from qtpy.QtCore import Qt, QSettings
import orjson as json
import os
from trigger_designer.qt.resource_manager import ResourceManager
from typing import Optional


class SettingsDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)
        self.rsm: ResourceManager = ResourceManager()
        self.settings = QSettings('Blue Octa', 'Trigger Designer')
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

    def load_settings(self):

        return {}

    def save_settings(self) -> None:
        settings = {
            "theme": self.theme_combo.currentText(),
            "grid_size": self.grid_size.value(),
            "show_grid": self.show_grid.isChecked()
        }

        # settings_file = os.path.join(os.path.dirname(
        #     __file__), "../resources/settings.json")
        settings_file = self.rsm._res_folder / "resources/qt/settings.json"

        os.makedirs(os.path.dirname(settings_file), exist_ok=True)
        settings_json = json.dumps(settings, option=json.OPT_INDENT_2)

        with open(settings_file, 'w') as f:
            f.write(settings_json.decode())

        qsettings = QSettings('Blue Octa', 'Trigger Designer')

        logger.info(settings)
        logger.debug(
            qsettings.allKeys()
        )

        theme = settings.get('theme', 'dark')
        print("🐍 File: models/settings_panel.py:106 | save_settings ~ theme", theme)
        grid_size = settings.get('grid_size', 20)
        show_grid = settings.get('show_grid', True)

        qsettings.setValue('theme', theme)
        print("🐍 File: models/settings_panel.py:111 | save_settings ~ theme", theme)

        style_sheet = self.rsm.load_theme(theme)
        print("🐍 File: models/settings_panel.py:114 | save_settings ~ theme", theme)

        QApplication.instance().setStyleSheet(style_sheet)

        self.accept()
