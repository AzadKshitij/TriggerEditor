"""Full colour-token editor for user themes.

Every colour token in :data:`trigger_designer.qt.theme_manager.TOKEN_GROUPS`
is editable; geometry and spacing stay owned by the design system. The editor
saves a complete resolved token set, so later changes to a built-in theme do
not silently alter a user's theme.
"""

from __future__ import annotations

from loguru import logger
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.theme_manager import (
    TOKEN_GROUPS,
    ThemeError,
    get_theme_manager,
    repolish,
)
from trigger_designer.qt.widgets.common.config_widgets import (
    ConfigSection,
    NoWheelComboBox,
    TextButton,
)
from trigger_designer.qt.widgets.common.theme_widgets import (
    ColorSwatchButton,
    ThemePreviewWidget,
    contrast_ratio,
)

#: Advisory contrast pairs: (label, foreground token, background token, target).
_CONTRAST_PAIRS = (
    ("Body text on base", "text_secondary", "background_primary", 4.5),
    ("Headings on base", "text_primary", "background_primary", 4.5),
    ("Muted on base", "text_tertiary", "background_primary", 3.0),
    ("Warning on base", "warning", "background_primary", 3.0),
)


class ThemeEditorDialog(QDialog):
    """Duplicate/edit a user theme's colour tokens with a live preview."""

    def __init__(self, theme_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manager = get_theme_manager()
        self._theme_id = theme_id
        theme = self._manager.theme(theme_id)
        if theme.error:
            QMessageBox.warning(
                self,
                "Theme unavailable",
                f"'{theme_id}' could not be loaded: {theme.error}",
            )
        self._original_tokens = dict(theme.tokens)
        self._tokens = dict(theme.tokens)
        self._appearance = theme.appearance
        self._name = theme.name
        self._rows: dict[str, tuple[ColorSwatchButton, QLineEdit]] = {}
        self._contrast_labels: list[QLabel] = []

        self.setObjectName("ThemeEditorDialog")
        self.setWindowTitle("Customize Theme")
        self.setMinimumSize(760, 560)
        self._build_ui()
        self._refresh_preview()
        self._refresh_contrast()

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(5, 5, 5, 5)
        outer.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(6)
        name_label = QLabel("Name")
        name_label.setObjectName("FieldLabel")
        header.addWidget(name_label)
        self.name_edit = QLineEdit(self._name)
        self.name_edit.setObjectName("ThemeNameEdit")
        self.name_edit.setMinimumWidth(180)
        self.name_edit.textChanged.connect(self._on_name_changed)
        header.addWidget(self.name_edit)

        appearance_label = QLabel("Appearance")
        appearance_label.setObjectName("FieldLabel")
        header.addWidget(appearance_label)
        self.appearance_combo = NoWheelComboBox()
        self.appearance_combo.setObjectName("ThemeAppearanceCombo")
        self.appearance_combo.addItems(["Dark", "Light"])
        self.appearance_combo.setCurrentText(
            "Light" if self._appearance == "light" else "Dark"
        )
        self.appearance_combo.currentTextChanged.connect(self._on_appearance_changed)
        header.addWidget(self.appearance_combo)
        header.addStretch(1)
        id_label = QLabel(f"id: {self._theme_id}")
        id_label.setObjectName("FieldHint")
        header.addWidget(id_label)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(6)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("ThemeEditorScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget(self.scroll_area)
        content.setObjectName("ThemeEditorContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)
        for group_title, rows in TOKEN_GROUPS:
            section = ConfigSection(group_title)
            for key, label in rows:
                section.addWidget(self._build_token_row(key, label))
            content_layout.addWidget(section)
        content_layout.addStretch(1)
        self.scroll_area.setWidget(content)
        body.addWidget(self.scroll_area, 3)

        side = QVBoxLayout()
        side.setSpacing(6)
        preview_label = QLabel("Preview")
        preview_label.setObjectName("SectionTitleText")
        side.addWidget(preview_label)
        self.preview = ThemePreviewWidget(self._tokens)
        side.addWidget(self.preview)

        preview_section = ConfigSection("Contrast")
        for label, _fg, _bg, _target in _CONTRAST_PAIRS:
            row = QLabel(label)
            row.setObjectName("ContrastLabel")
            self._contrast_labels.append(row)
            preview_section.addWidget(row)
        side.addWidget(preview_section)
        side.addStretch(1)
        body.addLayout(side, 2)
        outer.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        revert = TextButton(
            "Revert Changes", "Restore the tokens from when this editor opened"
        )
        revert.clicked.connect(self._revert)
        footer.addWidget(revert)
        footer.addStretch(1)
        cancel = TextButton("Cancel")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        save = TextButton("Save Theme", "Save this theme and apply it")
        save.setObjectName("PrimaryButton")
        save.clicked.connect(self._save)
        footer.addWidget(save)
        outer.addLayout(footer)

    def _build_token_row(self, key: str, label: str) -> QWidget:
        row = QWidget()
        row.setObjectName("ThemeTokenRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        name = QLabel(label)
        name.setObjectName("FieldLabel")
        name.setMinimumWidth(120)
        layout.addWidget(name)

        swatch = ColorSwatchButton(str(self._tokens.get(key, "#000000")))
        swatch.set_tokens(self._tokens)
        swatch.setToolTip(f"{label} — choose colour")
        swatch.setAccessibleName(f"{label} colour")
        layout.addWidget(swatch)

        hex_edit = QLineEdit(str(self._tokens.get(key, "")))
        hex_edit.setObjectName("ColorHexEdit")
        hex_edit.setFixedWidth(92)
        hex_edit.setToolTip("Hex colour, e.g. #1e242a or #AARRGGBB")
        layout.addWidget(hex_edit)
        layout.addStretch(1)

        swatch.colorChanged.connect(
            lambda value, k=key, e=hex_edit: self._on_swatch_changed(k, value, e)
        )
        hex_edit.editingFinished.connect(
            lambda k=key, e=hex_edit, s=swatch: self._on_hex_changed(k, e, s)
        )
        self._rows[key] = (swatch, hex_edit)
        return row

    # -- editing ----------------------------------------------------------
    def _on_name_changed(self, text: str) -> None:
        self._name = text

    def _on_appearance_changed(self, text: str) -> None:
        self._appearance = "light" if text.lower() == "light" else "dark"

    def _on_swatch_changed(self, key: str, value: str, hex_edit: QLineEdit) -> None:
        self._tokens[key] = value
        hex_edit.setText(value)
        self._refresh_preview()
        self._refresh_contrast()

    def _on_hex_changed(
        self, key: str, hex_edit: QLineEdit, swatch: ColorSwatchButton
    ) -> None:
        text = hex_edit.text().strip()
        color = QColor(text)
        if not color.isValid():
            hex_edit.setText(str(self._tokens.get(key, "")))
            return
        value = (
            color.name(QColor.NameFormat.HexArgb)
            if color.alpha() < 255
            else color.name(QColor.NameFormat.HexRgb)
        )
        self._tokens[key] = value
        swatch.set_color(color)
        hex_edit.setText(value)
        self._refresh_preview()
        self._refresh_contrast()

    def _revert(self) -> None:
        self._tokens = dict(self._original_tokens)
        for key, (swatch, hex_edit) in self._rows.items():
            value = self._tokens.get(key, "")
            swatch.set_color(str(value))
            hex_edit.setText(str(value))
        self._refresh_preview()
        self._refresh_contrast()

    def _refresh_preview(self) -> None:
        self.preview.set_tokens(self._tokens)
        for swatch, _hex in self._rows.values():
            swatch.set_tokens(self._tokens)

    def _refresh_contrast(self) -> None:
        for label, (text, fg, bg, target) in zip(
            self._contrast_labels, _CONTRAST_PAIRS
        ):
            ratio = contrast_ratio(
                self._tokens.get(fg, "#000000"), self._tokens.get(bg, "#ffffff")
            )
            ok = ratio >= target
            label.setText(f"{text} — {ratio:.1f}:1")
            label.setProperty("tone", "ok" if ok else "warn")
            repolish(label)

    # -- save -------------------------------------------------------------
    def _save(self) -> None:
        name = self.name_edit.text().strip() or self._theme_id
        if not self._tokens:
            QMessageBox.warning(
                self, "Theme not saved", "The theme has no colour tokens."
            )
            return
        try:
            self._manager.save_user_theme(
                self._theme_id, name, self._appearance, self._tokens
            )
        except (OSError, ThemeError) as exc:
            logger.error(f"Unable to save theme '{self._theme_id}': {exc}")
            QMessageBox.warning(self, "Theme not saved", str(exc))
            return
        self._original_tokens = dict(self._tokens)
        self.accept()
