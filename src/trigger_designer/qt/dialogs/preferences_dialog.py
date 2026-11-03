"""Preferences dialog: appearance, layout, editor, node editor colours, shortcuts.

Replaces the old tabbed ``SettingsDialog``. Theme selection previews live;
Cancel restores the theme and accent that were active when the dialog
opened. Layout, editor and node-colour changes apply immediately, matching
the live-by-default rule (docs/DESIGN_SYSTEM.md §6).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from qtpy.QtCore import QSize, Qt, QUrl
from qtpy.QtGui import QDesktopServices, QKeySequence
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.dialogs.theme_editor_dialog import ThemeEditorDialog
from trigger_designer.qt.helpers import node_arrange
from trigger_designer.qt.helpers import shortcuts as shortcut_store
from trigger_designer.qt.helpers.recent_files import RecentFilesManager
from trigger_designer.qt.node_editor_colors import (
    DEFAULT_EDGE_COLORS,
    DEFAULT_SOCKET_COLORS,
    apply_node_editor_colors,
    load_node_editor_colors,
    refresh_open_scenes,
    save_node_editor_colors,
)
from trigger_designer.qt.preferences import app_data_dir, get_preferences
from trigger_designer.qt.render_settings import ELEMENTS as RENDER_ELEMENTS
from trigger_designer.qt.render_settings import MODES as RENDER_MODES
from trigger_designer.qt.theme_manager import (
    SYSTEM_THEME_ID,
    ThemeError,
    get_theme_manager,
    repolish,
)
from trigger_designer.qt.widgets.common.config_widgets import (
    ConfigSection,
    IconButton,
    NoWheelComboBox,
    TextButton,
)
from trigger_designer.qt.widgets.common.theme_widgets import (
    ColorSwatchButton,
    ThemePreviewWidget,
)

if TYPE_CHECKING:
    from trigger_designer.qt.main_window import TriggerWindow

_PAGES = (
    "Appearance",
    "Layout",
    "Editor",
    "Node Editor",
    "Shortcuts",
    "General",
)

_ACCENT_PRESETS = (
    "#5680c2",
    "#0078d4",
    "#7c5cbf",
    "#3f9e63",
    "#c99a3c",
    "#e0686c",
    "#5ba8d6",
)


_FONT_SIZE_MIN = 8
_FONT_SIZE_MAX = 20


class PreferencesDialog(QDialog):
    """One dialog for every user preference."""

    def __init__(self, parent: TriggerWindow | None = None) -> None:
        super().__init__(parent)
        self._window: TriggerWindow | None = parent
        self._prefs = get_preferences()
        self._manager = get_theme_manager()
        self._applied_theme = self._manager.requested_theme_id()
        self._applied_accent = self._manager.requested_accent()
        self._applied_font_size = self._manager.requested_font_size()
        self._accent_swatches: list[ColorSwatchButton] = []
        self._node_swatches: dict[tuple[str, str], ColorSwatchButton] = {}

        self.setObjectName("PreferencesDialog")
        self.setWindowTitle("Preferences")
        self.setMinimumSize(660, 520)
        self._build_ui()
        self._load_pages()

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = QListWidget(self)
        self.sidebar.setObjectName("PreferencesSidebar")
        self.sidebar.setFixedWidth(168)
        for page in _PAGES:
            item = QListWidgetItem(page)
            item.setData(Qt.ItemDataRole.UserRole, page)
            self.sidebar.addItem(item)
        self.sidebar.currentRowChanged.connect(self._on_page_changed)
        outer.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(10, 8, 10, 8)
        right.setSpacing(6)

        self.stack = QStackedWidget(self)
        self.stack.setObjectName("PreferencesPages")
        self.appearance_page = self._build_appearance_page()
        self.layout_page = self._build_layout_page()
        self.editor_page = self._build_editor_page()
        self.node_editor_page = self._build_node_editor_page()
        self.shortcuts_page = self._build_shortcuts_page()
        self.general_page = self._build_general_page()
        for page in (
            self.appearance_page,
            self.layout_page,
            self.editor_page,
            self.node_editor_page,
            self.shortcuts_page,
            self.general_page,
        ):
            self.stack.addWidget(self._scroll_page(page))
        right.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        footer.addStretch(1)
        cancel = TextButton("Cancel", "Discard unsaved theme changes")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        apply_button = TextButton("Apply", "Apply theme changes without closing")
        apply_button.clicked.connect(self._apply_changes)
        footer.addWidget(apply_button)
        ok = TextButton("OK", "Save preferences and close")
        ok.setObjectName("PrimaryButton")
        ok.clicked.connect(self.accept)
        footer.addWidget(ok)
        right.addLayout(footer)

        outer.addLayout(right, 1)
        self.sidebar.setCurrentRow(0)

    def _scroll_page(self, page: QWidget) -> QScrollArea:
        """Let one preferences page scroll instead of squeezing its controls.

        The dialog opens at its minimum size while a page's natural height
        follows the application font and its number of sections. Appearance
        alone needs more room than the body has for the 210px preview, the
        theme list and the accent and font sections; without a scroll area the
        layout runs out of room and paints controls over one another.
        """
        scroll = QScrollArea(self)
        scroll.setObjectName("PreferencesScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(page)
        return scroll

    # -- Appearance -------------------------------------------------------
    def _build_appearance_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PreferencesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.preview = ThemePreviewWidget()
        layout.addWidget(self.preview)

        theme_section = ConfigSection("Theme")
        theme_body = QHBoxLayout()
        theme_body.setSpacing(6)
        self.theme_list = QListWidget(self)
        self.theme_list.setObjectName("ThemeList")
        self.theme_list.setFixedHeight(148)
        self.theme_list.currentItemChanged.connect(self._on_theme_selected)
        theme_body.addWidget(self.theme_list, 1)

        # The four actions sit beside the list, not under it: a row of text
        # buttons needs more width than the page has once the vertical
        # scrollbar is showing at the dialog's minimum width. A rail also
        # keeps each label on one line when the application font grows.
        theme_actions = QVBoxLayout()
        theme_actions.setSpacing(4)
        self.customize_button = TextButton(
            "Customize…", "Duplicate and edit the selected theme"
        )
        self.customize_button.clicked.connect(self._customize_theme)
        theme_actions.addWidget(self.customize_button)
        self.import_button = TextButton("Import…", "Import a theme JSON file")
        self.import_button.clicked.connect(self._import_theme)
        theme_actions.addWidget(self.import_button)
        self.export_button = TextButton("Export…", "Export the selected theme")
        self.export_button.clicked.connect(self._export_theme)
        theme_actions.addWidget(self.export_button)
        self.delete_button = TextButton("Delete", "Delete the selected user theme")
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.clicked.connect(self._delete_theme)
        theme_actions.addWidget(self.delete_button)
        theme_actions.addStretch(1)
        theme_body.addLayout(theme_actions)
        theme_section.addLayout(theme_body)

        hint = QLabel(
            "Built-in themes are read-only; Customize makes an editable copy."
        )
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        theme_section.addWidget(hint)
        layout.addWidget(theme_section)

        accent_section = ConfigSection("Accent")
        accent_row = QHBoxLayout()
        accent_row.setSpacing(4)
        for preset in _ACCENT_PRESETS:
            swatch = ColorSwatchButton(
                preset,
                swatch_size=QSize(24, 22),
                object_name="AccentSwatch",
                open_dialog=False,
            )
            swatch.setToolTip(f"Use accent {preset}")
            swatch.setAccessibleName(f"Accent {preset}")
            swatch.colorChanged.connect(lambda value: self._set_accent(value))
            self._accent_swatches.append(swatch)
            accent_row.addWidget(swatch)
        self.custom_accent = ColorSwatchButton("#5680c2", object_name="AccentSwatch")
        self.custom_accent.setToolTip("Choose a custom accent colour")
        self.custom_accent.setAccessibleName("Custom accent colour")
        self.custom_accent.colorChanged.connect(lambda value: self._set_accent(value))
        accent_row.addWidget(self.custom_accent)
        accent_row.addStretch(1)
        reset_accent = TextButton("Theme Default", "Use the theme's own accent")
        reset_accent.clicked.connect(lambda: self._set_accent(""))
        accent_row.addWidget(reset_accent)
        accent_section.addLayout(accent_row)
        layout.addWidget(accent_section)

        font_section = ConfigSection("Font size")
        font_row = QHBoxLayout()
        font_row.setSpacing(6)
        font_label = QLabel("Application text")
        font_label.setObjectName("FieldLabel")
        font_row.addWidget(font_label)
        self.font_size_spin = QSpinBox(self)
        self.font_size_spin.setObjectName("FontSizeSpin")
        self.font_size_spin.setRange(_FONT_SIZE_MIN, _FONT_SIZE_MAX)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setValue(self._current_font_size())
        self.font_size_spin.valueChanged.connect(self._set_font_size)
        font_row.addWidget(self.font_size_spin)
        font_row.addStretch(1)
        reset_font = TextButton("Default", "Use the system font size")
        reset_font.clicked.connect(lambda: self._set_font_size(0))
        font_row.addWidget(reset_font)
        font_section.addLayout(font_row)
        layout.addWidget(font_section)
        layout.addStretch(1)
        return page

    # -- Layout -----------------------------------------------------------
    def _build_layout_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PreferencesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        startup = ConfigSection("Startup")
        self.restore_layout_check = QCheckBox(
            "Restore window and dock layout on startup"
        )
        self.restore_layout_check.toggled.connect(
            lambda value: self._prefs.set("layout/restore", bool(value))
        )
        startup.addWidget(self.restore_layout_check)
        self.restore_session_check = QCheckBox("Reopen files from the last session")
        self.restore_session_check.toggled.connect(
            lambda value: self._prefs.set("layout/session", bool(value))
        )
        startup.addWidget(self.restore_session_check)
        session_hint = QLabel(
            "The session file list is always kept; it is only reopened when this is on."
        )
        session_hint.setObjectName("FieldHint")
        session_hint.setWordWrap(True)
        startup.addWidget(session_hint)
        layout.addWidget(startup)

        saved = ConfigSection("Saved Layout")
        saved_row = QHBoxLayout()
        saved_row.setSpacing(4)
        save_button = TextButton(
            "Save Current Layout", "Persist the current arrangement"
        )
        save_button.clicked.connect(self._save_layout)
        saved_row.addWidget(save_button)
        reset_button = TextButton("Reset Layout", "Restore the default arrangement")
        reset_button.clicked.connect(self._reset_layout)
        saved_row.addWidget(reset_button)
        saved_row.addStretch(1)
        saved.addLayout(saved_row)
        layout.addWidget(saved)
        layout.addStretch(1)
        return page

    # -- Editor -----------------------------------------------------------
    def _build_editor_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PreferencesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        canvas = ConfigSection("Canvas")
        grid_row = QHBoxLayout()
        grid_label = QLabel("Grid size")
        grid_label.setObjectName("FieldLabel")
        grid_row.addWidget(grid_label)
        self.grid_size_spin = QSpinBox(self)
        self.grid_size_spin.setObjectName("GridSizeSpin")
        self.grid_size_spin.setRange(10, 100)
        self.grid_size_spin.setSuffix(" px")
        self.grid_size_spin.valueChanged.connect(self._on_grid_size_changed)
        grid_row.addWidget(self.grid_size_spin)
        grid_row.addStretch(1)
        canvas.addLayout(grid_row)

        self.show_grid_check = QCheckBox("Show grid")
        self.show_grid_check.toggled.connect(self._on_show_grid_changed)
        canvas.addWidget(self.show_grid_check)

        self.snap_to_grid_check = QCheckBox("Snap nodes to the grid while dragging")
        self.snap_to_grid_check.setToolTip(
            "Hold Alt while dragging a node to move it freely."
        )
        self.snap_to_grid_check.toggled.connect(self._on_snap_to_grid_changed)
        canvas.addWidget(self.snap_to_grid_check)
        layout.addWidget(canvas)

        rendering = ConfigSection("Rendering")
        threshold_row = QHBoxLayout()
        threshold_row.setSpacing(6)
        threshold_label = QLabel("Simplify below")
        threshold_label.setObjectName("FieldLabel")
        threshold_label.setMinimumWidth(120)
        threshold_row.addWidget(threshold_label)
        self.render_detail_spin = QSpinBox(self)
        self.render_detail_spin.setObjectName("RenderDetailSpin")
        self.render_detail_spin.setRange(0, 100)
        self.render_detail_spin.setSuffix(" %")
        self.render_detail_spin.setToolTip(
            "Below this zoom the canvas drops the parts of a node it can spare. "
            "0 % keeps every node fully drawn."
        )
        self.render_detail_spin.valueChanged.connect(self._on_render_threshold_changed)
        threshold_row.addWidget(self.render_detail_spin)
        threshold_row.addStretch(1)
        rendering.addLayout(threshold_row)

        self.render_detail_combos: dict[str, NoWheelComboBox] = {}
        for key, title in RENDER_ELEMENTS:
            row = QHBoxLayout()
            row.setSpacing(6)
            label = QLabel(title)
            label.setObjectName("FieldLabel")
            label.setMinimumWidth(120)
            row.addWidget(label)
            combo = NoWheelComboBox(self)
            combo.setObjectName(f"RenderDetail{key.capitalize()}Combo")
            combo.setToolTip(
                f"{title}: Always draws it at every zoom, Never hides it at "
                "every zoom, and Auto follows the zoom threshold."
            )
            for mode in RENDER_MODES:
                combo.addItem(mode.capitalize(), mode)
            combo.currentIndexChanged.connect(
                lambda _index, k=key: self._on_render_mode_changed(k)
            )
            row.addWidget(combo)
            row.addStretch(1)
            rendering.addLayout(row)
            self.render_detail_combos[key] = combo

        layout.addWidget(rendering)
        layout.addStretch(1)
        return page

    # -- Node Editor ------------------------------------------------------
    def _build_node_editor_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PreferencesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        colors = load_node_editor_colors()
        for group_title, group_key, defaults in (
            ("Edges", "edges", DEFAULT_EDGE_COLORS),
            ("Sockets", "sockets", DEFAULT_SOCKET_COLORS),
        ):
            section = ConfigSection(group_title)
            for key, default in defaults.items():
                row = QHBoxLayout()
                row.setSpacing(6)
                label = QLabel(key.replace("_", " ").capitalize())
                label.setObjectName("FieldLabel")
                label.setMinimumWidth(120)
                row.addWidget(label)
                swatch = ColorSwatchButton(colors[group_key].get(key, default))
                swatch.setToolTip(f"{group_title[:-1]} {key} colour")
                swatch.setAccessibleName(f"{group_title[:-1]} {key} colour")
                swatch.colorChanged.connect(
                    lambda value, g=group_key, k=key: self._on_node_color_changed(
                        g, k, value
                    )
                )
                self._node_swatches[(group_key, key)] = swatch
                row.addWidget(swatch)
                row.addStretch(1)
                section.addLayout(row)
            layout.addWidget(section)

        reset_row = QHBoxLayout()
        reset_button = TextButton("Reset Node Colours", "Restore the library defaults")
        reset_button.clicked.connect(self._reset_node_colors)
        reset_row.addWidget(reset_button)
        reset_row.addStretch(1)
        layout.addLayout(reset_row)
        layout.addStretch(1)
        return page

    # -- Shortcuts --------------------------------------------------------
    def _build_shortcuts_page(self) -> QWidget:
        """One key sequence per Arrange command, edited in place.

        The page scrolls: nine rows plus their reset buttons overflow a
        520px dialog once the application font grows. Changes save and apply
        as they are made (docs/DESIGN_SYSTEM.md §6); the reset button beside
        a row only exists because a key sequence has no obvious "empty"
        state once the field is filled.
        """
        page = QWidget()
        page.setObjectName("PreferencesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        hint = QLabel(
            "Click a field and press the keys. A shortcut needs Ctrl, Alt or "
            "Shift, or a function key; function keys are allowed on their own. "
            "Backspace clears one."
        )
        hint.setObjectName("FieldHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        section = ConfigSection("Arranging nodes")
        self.shortcut_editors: dict[str, QKeySequenceEdit] = {}
        for command in node_arrange.SHORTCUT_COMMANDS:
            row = QHBoxLayout()
            row.setSpacing(6)
            label = QLabel(command.label)
            label.setObjectName("FieldLabel")
            label.setMinimumWidth(180)
            row.addWidget(label)

            editor = QKeySequenceEdit(page)
            editor.setObjectName("ShortcutEditor")
            editor.setMaximumSequenceLength(1)
            editor.setToolTip(f"Shortcut for {command.label}")
            editor.setAccessibleName(f"Shortcut for {command.label}")
            editor.keySequenceChanged.connect(
                lambda _sequence, command_id=command.id: self._set_shortcut_error("")
            )
            editor.editingFinished.connect(
                lambda command_id=command.id: self._commit_shortcut(command_id)
            )
            row.addWidget(editor, 1)
            self.shortcut_editors[command.id] = editor

            reset = IconButton.themed(
                f"Restore the default shortcut for {command.label}",
                rsm_icon=self._shortcut_icon(),
                parent=page,
            )
            reset.clicked.connect(
                lambda _checked=False, command_id=command.id: (
                    self._restore_default_shortcut(command_id)
                )
            )
            row.addWidget(reset)
            section.addLayout(row)

        layout.addWidget(section)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        reset_all = TextButton(
            "Restore Defaults", "Put every Arrange shortcut back to its default"
        )
        reset_all.clicked.connect(self._restore_all_shortcuts)
        footer.addWidget(reset_all)
        footer.addStretch(1)
        layout.addLayout(footer)

        self.shortcut_error = QLabel("")
        self.shortcut_error.setObjectName("ShortcutError")
        self.shortcut_error.setWordWrap(True)
        self.shortcut_error.hide()
        layout.addWidget(self.shortcut_error)
        layout.addStretch(1)
        return page

    def _shortcut_icon(self):
        """The glyph shared by the per-row reset buttons."""
        try:
            from trigger_designer.qt.resource_manager import ResourceManager

            return ResourceManager().get("icon_refresh")
        except Exception as exc:  # noqa: BLE001 - icon lookup is advisory
            logger.debug(f"Reset icon unavailable: {exc}")
            return None

    # -- General ----------------------------------------------------------
    def _build_general_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("PreferencesPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        startup = ConfigSection("General")
        self.welcome_check = QCheckBox("Show the welcome dialog on startup")
        self.welcome_check.toggled.connect(self._on_welcome_changed)
        startup.addWidget(self.welcome_check)

        recent_row = QHBoxLayout()
        recent_label = QLabel("Recent files")
        recent_label.setObjectName("FieldLabel")
        recent_row.addWidget(recent_label)
        self.recent_limit_spin = QSpinBox(self)
        self.recent_limit_spin.setObjectName("RecentLimitSpin")
        self.recent_limit_spin.setRange(1, 50)
        self.recent_limit_spin.valueChanged.connect(self._on_recent_limit_changed)
        recent_row.addWidget(self.recent_limit_spin)
        recent_row.addStretch(1)
        clear_button = TextButton("Clear Recent Files", "Forget every recent path")
        clear_button.clicked.connect(self._clear_recents)
        recent_row.addWidget(clear_button)
        startup.addLayout(recent_row)

        folder_row = QHBoxLayout()
        open_folder = TextButton(
            "Open Preferences Folder",
            "Open the folder with preferences.ini and user themes",
        )
        open_folder.clicked.connect(self._open_data_folder)
        folder_row.addWidget(open_folder)
        folder_row.addStretch(1)
        startup.addLayout(folder_row)

        errors = ConfigSection("Error messages")
        self.continue_check = QCheckBox(
            "Keep running independent branches after a failure"
        )
        self.continue_check.toggled.connect(self._on_continue_changed)
        errors.addWidget(self.continue_check)

        self.redact_check = QCheckBox("Hide data values in error messages")
        self.redact_check.toggled.connect(self._on_redact_changed)
        errors.addWidget(self.redact_check)

        self.locate_check = QCheckBox("Find the offending row for conversion errors")
        self.locate_check.toggled.connect(self._on_locate_changed)
        errors.addWidget(self.locate_check)

        cap_row = QHBoxLayout()
        cap_label = QLabel("Row search limit")
        cap_label.setObjectName("FieldLabel")
        cap_row.addWidget(cap_label)
        self.locate_cap_spin = QSpinBox(self)
        self.locate_cap_spin.setObjectName("LocateRowCapSpin")
        self.locate_cap_spin.setRange(100_000, 100_000_000)
        self.locate_cap_spin.setSingleStep(100_000)
        self.locate_cap_spin.valueChanged.connect(self._on_locate_cap_changed)
        cap_row.addWidget(self.locate_cap_spin)
        cap_row.addStretch(1)
        errors.addLayout(cap_row)

        audit = self._build_audit_section()
        engagement = self._build_engagement_section()

        danger = ConfigSection("Reset")
        reset_all = TextButton(
            "Reset All Preferences",
            "Reset themes, layout, editor and node colours to defaults",
        )
        reset_all.setObjectName("DangerButton")
        reset_all.clicked.connect(self._reset_all)
        danger.addWidget(reset_all)
        danger_hint = QLabel("User themes are kept; only preferences are reset.")
        danger_hint.setObjectName("FieldHint")
        danger.addWidget(danger_hint)
        layout.addWidget(startup)
        layout.addWidget(errors)
        layout.addWidget(audit)
        layout.addWidget(engagement)
        layout.addWidget(danger)
        layout.addStretch(1)
        return page

    #: (attribute, preference key, label, placeholder) of the engagement fields.
    _ENGAGEMENT_FIELDS = (
        ("engagement_client_edit", "engagement/client_name", "Client", "Client name"),
        (
            "engagement_name_edit",
            "engagement/engagement_name",
            "Engagement",
            "Engagement or audit name",
        ),
        ("engagement_period_edit", "engagement/period", "Period", "Period covered"),
        (
            "engagement_preparer_edit",
            "engagement/preparer",
            "Prepared by",
            "Defaults to your Windows user name",
        ),
    )

    def _build_engagement_section(self) -> ConfigSection:
        """Defaults every Workpaper Output node and the workpaper export start from."""
        section = ConfigSection("Engagement")
        for attribute, key, label, placeholder in self._ENGAGEMENT_FIELDS:
            row = QHBoxLayout()
            caption = QLabel(label)
            caption.setObjectName("FieldLabel")
            row.addWidget(caption)
            edit = QLineEdit(self)
            edit.setObjectName(attribute)
            edit.setMinimumHeight(30)
            edit.setPlaceholderText(placeholder)
            edit.setAccessibleName(label)
            edit.editingFinished.connect(
                lambda edit=edit, key=key: self._prefs.set(key, edit.text().strip())
            )
            setattr(self, attribute, edit)
            row.addWidget(edit, 1)
            section.addLayout(row)

        logo_row = QHBoxLayout()
        logo_label = QLabel("Logo")
        logo_label.setObjectName("FieldLabel")
        logo_row.addWidget(logo_label)
        self.engagement_logo_edit = QLineEdit(self)
        self.engagement_logo_edit.setObjectName("engagement_logo_edit")
        self.engagement_logo_edit.setMinimumHeight(30)
        self.engagement_logo_edit.setPlaceholderText("PNG or JPG shown on the Summary")
        self.engagement_logo_edit.setAccessibleName("Logo")
        self.engagement_logo_edit.editingFinished.connect(self._on_logo_edited)
        logo_row.addWidget(self.engagement_logo_edit, 1)
        browse = TextButton("Browse", "Choose the logo image for workpapers")
        browse.clicked.connect(self._browse_logo)
        logo_row.addWidget(browse)
        section.addLayout(logo_row)
        return section

    def _load_engagement_section(self) -> None:
        for attribute, key, *_rest in self._ENGAGEMENT_FIELDS:
            getattr(self, attribute).setText(str(self._prefs.get(key, "") or ""))
        self.engagement_logo_edit.setText(
            str(self._prefs.get("engagement/logo_path", "") or "")
        )

    def _on_logo_edited(self) -> None:
        self._prefs.set(
            "engagement/logo_path", self.engagement_logo_edit.text().strip()
        )

    def _browse_logo(self) -> None:
        chosen, _selected = QFileDialog.getOpenFileName(
            self,
            "Workpaper logo",
            self.engagement_logo_edit.text() or "",
            "Images (*.png *.jpg *.jpeg)",
        )
        if chosen:
            self.engagement_logo_edit.setText(chosen)
            self._on_logo_edited()

    #: (attribute, preference key, label, tooltip) of the audit-trail checkboxes.
    _AUDIT_CHECKS = (
        (
            "audit_record_check",
            "audit/record_runs",
            "Record every run (run history)",
            "Write a tamper-evident record next to the workflow after each Run",
        ),
        (
            "audit_identity_check",
            "audit/record_identity",
            "Record the user and machine name",
            "Off: the user and machine fields of a record stay empty",
        ),
        (
            "audit_hash_inputs_check",
            "audit/hash_inputs",
            "Fingerprint input files (SHA-256)",
            "Hash each input file before the node reads it",
        ),
        (
            "audit_hash_outputs_check",
            "audit/hash_outputs",
            "Fingerprint output files (SHA-256)",
            "Hash each output file after it is written",
        ),
        (
            "audit_embed_check",
            "audit/embed_code",
            "Store the generated code in each record",
            "The code hash is always recorded; this keeps the text itself",
        ),
        (
            "audit_warn_check",
            "audit/warn_on_input_change",
            "Warn when an input changed since the previous run",
            "Adds one line per changed file to the Logging dock; never blocks a run",
        ),
    )

    #: Row-count choices: stored value, visible label.
    _AUDIT_COUNT_MODES = (
        ("auto", "Auto"),
        ("all", "All nodes"),
        ("sink", "Sinks only"),
        ("off", "Off"),
    )

    def _build_audit_section(self) -> ConfigSection:
        section = ConfigSection("Audit trail")
        for attribute, key, label, tip in self._AUDIT_CHECKS:
            check = QCheckBox(label)
            check.setObjectName(attribute)
            check.setToolTip(tip)
            check.toggled.connect(lambda value, key=key: self._prefs.set(key, value))
            setattr(self, attribute, check)
            section.addWidget(check)

        folder_row = QHBoxLayout()
        folder_label = QLabel("Run log folder")
        folder_label.setObjectName("FieldLabel")
        folder_row.addWidget(folder_label)
        self.audit_dir_edit = QLineEdit(self)
        self.audit_dir_edit.setObjectName("AuditRunLogDir")
        self.audit_dir_edit.setMinimumHeight(30)
        self.audit_dir_edit.setPlaceholderText("Next to each workflow (default)")
        self.audit_dir_edit.setToolTip(
            "Keep every run log here instead of next to the workflow file"
        )
        self.audit_dir_edit.setAccessibleName("Run log folder")
        self.audit_dir_edit.editingFinished.connect(self._on_audit_dir_edited)
        folder_row.addWidget(self.audit_dir_edit, 1)
        browse = TextButton("Browse", "Choose the folder that holds the run logs")
        browse.clicked.connect(self._browse_audit_dir)
        folder_row.addWidget(browse)
        section.addLayout(folder_row)

        counts_row = QHBoxLayout()
        counts_label = QLabel("Row counts")
        counts_label.setObjectName("FieldLabel")
        counts_row.addWidget(counts_label)
        self.audit_counts_combo = NoWheelComboBox(self)
        self.audit_counts_combo.setObjectName("AuditRowCounts")
        self.audit_counts_combo.setMinimumHeight(30)
        self.audit_counts_combo.setAccessibleName("Row counts")
        self.audit_counts_combo.setToolTip(
            "Auto counts every node for small inputs and only sources and "
            "outputs for large ones"
        )
        for value, text in self._AUDIT_COUNT_MODES:
            self.audit_counts_combo.addItem(text, value)
        self.audit_counts_combo.currentIndexChanged.connect(self._on_audit_counts)
        counts_row.addWidget(self.audit_counts_combo, 1)
        section.addLayout(counts_row)

        for attribute, key, label, low, high in (
            (
                "audit_threshold_spin",
                "audit/exact_counts_max_mb",
                "Count every node up to (MB)",
                0,
                1_000_000,
            ),
            (
                "audit_hash_max_spin",
                "audit/hash_max_mb",
                "Skip hashing files above (MB)",
                0,
                10_000_000,
            ),
        ):
            row = QHBoxLayout()
            caption = QLabel(label)
            caption.setObjectName("FieldLabel")
            row.addWidget(caption)
            spin = QSpinBox(self)
            spin.setObjectName(attribute)
            spin.setRange(low, high)
            spin.setAccessibleName(label)
            spin.valueChanged.connect(
                lambda value, key=key: self._prefs.set(key, value)
            )
            setattr(self, attribute, spin)
            row.addWidget(spin)
            row.addStretch(1)
            section.addLayout(row)
        return section

    def _load_audit_section(self) -> None:
        for attribute, key, *_rest in self._AUDIT_CHECKS:
            check = getattr(self, attribute)
            check.blockSignals(True)
            check.setChecked(bool(self._prefs.get(key, True)))
            check.blockSignals(False)
        self.audit_dir_edit.setText(str(self._prefs.get("audit/run_log_dir", "") or ""))
        current = str(self._prefs.get("audit/row_counts", "auto") or "auto")
        index = self.audit_counts_combo.findData(current)
        self.audit_counts_combo.blockSignals(True)
        self.audit_counts_combo.setCurrentIndex(max(0, index))
        self.audit_counts_combo.blockSignals(False)
        for attribute, key, default in (
            ("audit_threshold_spin", "audit/exact_counts_max_mb", 256),
            ("audit_hash_max_spin", "audit/hash_max_mb", 2048),
        ):
            spin = getattr(self, attribute)
            spin.blockSignals(True)
            spin.setValue(int(self._prefs.get(key, default) or 0))
            spin.blockSignals(False)

    def _on_audit_counts(self, _index: int) -> None:
        self._prefs.set("audit/row_counts", str(self.audit_counts_combo.currentData()))

    def _on_audit_dir_edited(self) -> None:
        self._prefs.set("audit/run_log_dir", self.audit_dir_edit.text().strip())

    def _browse_audit_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Run log folder", self.audit_dir_edit.text() or ""
        )
        if chosen:
            self.audit_dir_edit.setText(chosen)
            self._on_audit_dir_edited()

    # -- state loading ----------------------------------------------------
    def _load_pages(self) -> None:
        self._reload_theme_list(self._manager.requested_theme_id())
        self.restore_layout_check.setChecked(
            bool(self._prefs.get("layout/restore", True))
        )
        self.restore_session_check.setChecked(
            bool(self._prefs.get("layout/session", False))
        )
        self.grid_size_spin.setValue(int(self._prefs.get("editor/grid_size", 20) or 20))
        self.show_grid_check.setChecked(bool(self._prefs.get("editor/show_grid", True)))
        self.snap_to_grid_check.setChecked(
            bool(self._prefs.get("editor/snap_to_grid", True))
        )
        self.font_size_spin.setValue(self._current_font_size())
        self._load_render_settings()
        self._load_shortcuts_page()
        recent = RecentFilesManager()
        self.welcome_check.setChecked(recent.is_welcome_enabled())
        self.recent_limit_spin.setValue(recent.max_items)
        self.continue_check.setChecked(
            bool(self._prefs.get("errors/continue_past_failure", True))
        )
        self.redact_check.setChecked(
            bool(self._prefs.get("errors/redact_values", False))
        )
        self.locate_check.setChecked(bool(self._prefs.get("errors/locate_rows", True)))
        self.locate_cap_spin.setValue(
            int(self._prefs.get("errors/locate_row_cap", 5_000_000) or 5_000_000)
        )
        self._load_audit_section()
        self._load_engagement_section()

    def _on_page_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)

    # -- theme list -------------------------------------------------------
    def _reload_theme_list(self, select_id: str | None = None) -> None:
        self.theme_list.blockSignals(True)
        self.theme_list.clear()
        system_item = QListWidgetItem("System — follow Windows appearance")
        system_item.setData(Qt.ItemDataRole.UserRole, SYSTEM_THEME_ID)
        self.theme_list.addItem(system_item)
        for theme in self._manager.available_themes():
            label = theme.name
            label += "  ·  Built-in" if theme.builtin else "  ·  My theme"
            if theme.error:
                label += "  ·  Failed to load"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, theme.id)
            item.setToolTip(
                theme.error or f"{theme.name} ({'dark' if theme.is_dark else 'light'})"
            )
            self.theme_list.addItem(item)
        self.theme_list.blockSignals(False)
        self._select_theme(select_id or self._manager.requested_theme_id())

    def _select_theme(self, theme_id: str) -> None:
        for index in range(self.theme_list.count()):
            item = self.theme_list.item(index)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == theme_id:
                self.theme_list.setCurrentItem(item)
                return
        self.theme_list.setCurrentRow(1)

    def _selected_theme_id(self) -> str | None:
        item = self.theme_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_theme_selected(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        theme_id = current.data(Qt.ItemDataRole.UserRole)
        try:
            self._manager.preview(theme_id)
        except ThemeError as exc:
            QMessageBox.warning(self, "Theme unavailable", str(exc))
            return
        self._refresh_preview()
        self._update_theme_buttons()

    def _update_theme_buttons(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            return
        theme = self._manager.theme(theme_id)
        user_theme = not theme.builtin and theme_id != SYSTEM_THEME_ID
        self.delete_button.setEnabled(user_theme)
        self.export_button.setEnabled(theme_id != SYSTEM_THEME_ID)
        self.customize_button.setEnabled(theme_id != SYSTEM_THEME_ID)

    def _refresh_preview(self) -> None:
        theme = self._manager.active_theme()
        self.preview.set_tokens(theme.tokens)
        accent = self._manager.requested_accent()
        for swatch in self._accent_swatches:
            active = bool(accent) and swatch.color_name().lower() == accent.lower()
            swatch.setProperty("selected", active)
            repolish(swatch)
        if accent:
            self.custom_accent.set_color(accent)

    # -- theme actions ----------------------------------------------------
    def _customize_theme(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            return
        theme = self._manager.theme(theme_id)
        if theme_id == SYSTEM_THEME_ID or theme.builtin:
            base_id = (
                ("light" if self._manager.system_appearance() == "light" else "dark")
                if theme_id == SYSTEM_THEME_ID
                else theme_id
            )
            default_name = f"{self._manager.theme(base_id).name} Custom"
            name, accepted = QInputDialog.getText(
                self,
                "Duplicate Theme",
                "Name for the editable copy:",
                text=default_name,
            )
            if not accepted or not name.strip():
                return
            duplicated = self._manager.duplicate_theme(base_id, name.strip())
            theme_id = duplicated.id
        dialog = ThemeEditorDialog(theme_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._reload_theme_list(theme_id)
            self._manager.preview(theme_id)
            self._refresh_preview()

    def _import_theme(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Import theme", "", "Theme files (*.json)"
        )
        if not path:
            return
        try:
            theme = self._manager.import_theme(path)
        except (ThemeError, OSError) as exc:
            logger.error(f"Theme import failed: {exc}")
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self._reload_theme_list(theme.id)
        self._manager.preview(theme.id)
        self._refresh_preview()

    def _export_theme(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None or theme_id == SYSTEM_THEME_ID:
            return
        theme = self._manager.theme(theme_id)
        default_path = str(Path.home() / f"{theme.id}.json")
        path, _filter = QFileDialog.getSaveFileName(
            self, "Export theme", default_path, "Theme files (*.json)"
        )
        if not path:
            return
        try:
            self._manager.export_theme(theme_id, path)
        except (ThemeError, OSError) as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def _delete_theme(self) -> None:
        theme_id = self._selected_theme_id()
        if theme_id is None:
            return
        theme = self._manager.theme(theme_id)
        if theme.builtin or theme_id == SYSTEM_THEME_ID:
            return
        answer = QMessageBox.question(
            self,
            "Delete theme",
            f'Delete the user theme "{theme.name}"?\nThis cannot be undone.',
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._manager.delete_user_theme(theme_id)
        self._manager.apply()
        self._reload_theme_list(self._manager.requested_theme_id())
        self._refresh_preview()

    # -- accent -----------------------------------------------------------
    def _set_accent(self, value: str) -> None:
        self._manager.set_accent(value)
        self.custom_accent.set_color(value or self._manager.token("accent_primary"))
        self._refresh_preview()

    # -- font size --------------------------------------------------------
    def _current_font_size(self) -> int:
        size = self._manager.requested_font_size() or round(
            self._manager.base_font_size()
        )
        return min(max(size, _FONT_SIZE_MIN), _FONT_SIZE_MAX)

    def _set_font_size(self, size: int) -> None:
        self._manager.set_font_size(size)
        self.font_size_spin.blockSignals(True)
        self.font_size_spin.setValue(self._current_font_size())
        self.font_size_spin.blockSignals(False)
        self._refresh_preview()

    # -- layout -----------------------------------------------------------
    def _save_layout(self) -> None:
        window = self._window
        if window is not None and hasattr(window, "saveCurrentLayout"):
            window.saveCurrentLayout()

    def _reset_layout(self) -> None:
        window = self._window
        if window is not None and hasattr(window, "resetLayout"):
            window.resetLayout()

    # -- editor -----------------------------------------------------------
    def _apply_canvas_settings(self) -> None:
        window = self._window
        if window is not None and hasattr(window, "apply_appearance"):
            window.apply_appearance()

    def _on_grid_size_changed(self, value: int) -> None:
        self._prefs.set("editor/grid_size", int(value))
        self._apply_canvas_settings()

    def _on_show_grid_changed(self, value: bool) -> None:
        self._prefs.set("editor/show_grid", bool(value))
        self._apply_canvas_settings()

    def _on_snap_to_grid_changed(self, value: bool) -> None:
        # Writes the preference and pushes the flag onto every open canvas;
        # the drag handler reads the flag off the graphics scene, not prefs.
        node_arrange.set_snap_enabled(enabled=bool(value))
        window = self._window
        if window is not None and hasattr(window, "syncSnapAction"):
            window.syncSnapAction()

    # -- shortcuts --------------------------------------------------------
    def _load_shortcuts_page(self) -> None:
        """Fill the editors from the stored map without recording edits."""
        self._shortcuts = shortcut_store.load_shortcuts(self._prefs)
        for command_id in self.shortcut_editors:
            self._set_shortcut_sequence(command_id, self._shortcuts.get(command_id, ""))
        self._set_shortcut_error("")

    def _set_shortcut_sequence(self, command_id: str, text: str) -> None:
        editor = self.shortcut_editors.get(command_id)
        if editor is None:
            return
        editor.blockSignals(True)
        editor.setKeySequence(shortcut_store.sequence(text))
        editor.blockSignals(False)

    def _commit_shortcut(self, command_id: str) -> bool:
        """Save one editor's sequence, or put the previous one back.

        :return: ``False`` when the sequence was refused, so ``accept`` can
            keep the dialog open with the reason visible.
        """
        editor = self.shortcut_editors.get(command_id)
        if editor is None:
            return True
        sequence = shortcut_store.normalize(
            editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
        )
        previous = self._shortcuts.get(command_id, "")
        if sequence == previous:
            self._set_shortcut_error("")
            return True

        assigned = dict(self._shortcuts)
        assigned[command_id] = sequence
        message = shortcut_store.conflict_message(
            sequence,
            command_id,
            assigned,
            shortcut_store.reserved_sequences(self._window),
        )
        if message:
            self._set_shortcut_error(message)
            self._set_shortcut_sequence(command_id, previous)
            return False

        self._shortcuts[command_id] = sequence
        shortcut_store.save_shortcut(self._prefs, command_id, sequence)
        self._set_shortcut_error("")
        self._apply_shortcuts()
        return True

    def _commit_all_shortcuts(self) -> bool:
        for command_id in self.shortcut_editors:
            if not self._commit_shortcut(command_id):
                return False
        return True

    def _restore_default_shortcut(self, command_id: str) -> None:
        default = shortcut_store.defaults().get(command_id, "")
        self._set_shortcut_sequence(command_id, default)
        self._commit_shortcut(command_id)

    def _restore_all_shortcuts(self) -> None:
        shortcut_store.reset_shortcuts(self._prefs)
        self._load_shortcuts_page()
        self._apply_shortcuts()

    def _apply_shortcuts(self) -> None:
        if self._window is not None:
            shortcut_store.apply_to_window(self._window, self._shortcuts)

    def _set_shortcut_error(self, message: str) -> None:
        label = getattr(self, "shortcut_error", None)
        if label is None:
            return
        label.setText(message)
        label.setVisible(bool(message))

    # -- rendering --------------------------------------------------------
    def _load_render_settings(self) -> None:
        """Fill the rendering controls without writing the values back."""
        self.render_detail_spin.blockSignals(True)
        self.render_detail_spin.setValue(
            int(self._prefs.get("editor/render_detail_threshold", 50) or 50)
        )
        self.render_detail_spin.blockSignals(False)
        for key, combo in self.render_detail_combos.items():
            # No fallback: the defaults live in the preference store, and the
            # label's default is not "auto" like the others.
            mode = str(self._prefs.get(f"editor/render_detail_{key}") or "auto")
            index = combo.findData(mode)
            combo.blockSignals(True)
            combo.setCurrentIndex(index if index >= 0 else combo.findData("auto"))
            combo.blockSignals(False)

    def _on_render_threshold_changed(self, value: int) -> None:
        self._prefs.set("editor/render_detail_threshold", int(value))
        self._apply_render_settings()

    def _on_render_mode_changed(self, key: str) -> None:
        combo = self.render_detail_combos.get(key)
        mode = combo.currentData() if combo is not None else None
        if mode:
            self._prefs.set(f"editor/render_detail_{key}", str(mode))
        self._apply_render_settings()

    def _apply_render_settings(self) -> None:
        window = self._window
        if window is not None and hasattr(window, "apply_render_settings"):
            window.apply_render_settings()

    # -- node colours -----------------------------------------------------
    def _node_colors(self) -> dict[str, dict[str, str]]:
        colors = load_node_editor_colors()
        for (group, key), swatch in self._node_swatches.items():
            colors[group][key] = swatch.color_name()
        return colors

    def _on_node_color_changed(self, group: str, key: str, value: str) -> None:
        self._persist_node_colors()

    def _persist_node_colors(self) -> None:
        colors = self._node_colors()
        save_node_editor_colors(colors)
        apply_node_editor_colors(colors)
        if self._window is not None:
            refresh_open_scenes(self._window)

    def _reset_node_colors(self) -> None:
        for (group, key), swatch in self._node_swatches.items():
            defaults = (
                DEFAULT_EDGE_COLORS if group == "edges" else DEFAULT_SOCKET_COLORS
            )
            swatch.set_color(defaults[key])
        self._persist_node_colors()

    # -- general ----------------------------------------------------------
    def _on_continue_changed(self, value: bool) -> None:
        self._prefs.set("errors/continue_past_failure", bool(value))

    def _on_redact_changed(self, value: bool) -> None:
        self._prefs.set("errors/redact_values", bool(value))

    def _on_locate_changed(self, value: bool) -> None:
        self._prefs.set("errors/locate_rows", bool(value))

    def _on_locate_cap_changed(self, value: int) -> None:
        self._prefs.set("errors/locate_row_cap", int(value))

    def _on_welcome_changed(self, value: bool) -> None:
        RecentFilesManager().set_welcome_enabled(bool(value))

    def _on_recent_limit_changed(self, value: int) -> None:
        RecentFilesManager().set_max_items(int(value))

    def _clear_recents(self) -> None:
        RecentFilesManager().clear()
        if self._window is not None and hasattr(self._window, "refresh_recent_menu"):
            self._window.refresh_recent_menu()

    def _open_data_folder(self) -> None:
        folder = app_data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _reset_all(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset all preferences",
            "Reset themes, layout, editor and node colours to defaults?\n"
            "User themes are kept.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._prefs.reset()
        self._manager.invalidate()
        self._manager.cancel_preview()
        self._manager.set_accent("", persist=True)
        self._manager.set_font_size(0)
        apply_node_editor_colors(
            {"edges": dict(DEFAULT_EDGE_COLORS), "sockets": dict(DEFAULT_SOCKET_COLORS)}
        )
        save_node_editor_colors(
            {"edges": dict(DEFAULT_EDGE_COLORS), "sockets": dict(DEFAULT_SOCKET_COLORS)}
        )
        window = self._window
        if window is not None and hasattr(window, "resetLayout"):
            window.resetLayout()
        if window is not None:
            refresh_open_scenes(window)
        self._applied_theme = "dark"
        self._applied_accent = ""
        self._applied_font_size = 0
        self._load_pages()
        self._reload_theme_list("dark")
        self._refresh_preview()
        self._apply_shortcuts()

    # -- commit / discard -------------------------------------------------
    def _apply_changes(self) -> None:
        self._manager.commit_preview()
        self._applied_theme = self._manager.requested_theme_id()
        self._applied_accent = self._manager.requested_accent()
        self._applied_font_size = self._manager.requested_font_size()
        self._refresh_preview()

    def accept(self) -> None:
        if not self._commit_all_shortcuts():
            return
        self._apply_changes()
        super().accept()

    def reject(self) -> None:
        # Theme changes only previewed: drop them. Accent is persisted on
        # change (live), so restore the accent that was active on open.
        self._manager.cancel_preview()
        if self._manager.requested_accent() != self._applied_accent:
            self._manager.set_accent(self._applied_accent)
        if self._manager.requested_font_size() != self._applied_font_size:
            self._manager.set_font_size(self._applied_font_size)
        self._manager.apply(persist=False)
        super().reject()
