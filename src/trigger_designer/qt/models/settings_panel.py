"""Deprecated import path for the Preferences dialog.

The old tabbed ``SettingsDialog`` wrote a second ``QSettings`` scope and a
dead ``settings.json``. New code opens
``trigger_designer.qt.dialogs.preferences_dialog.PreferencesDialog``; this
module only keeps older imports working.
"""

from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog
from trigger_designer.qt.widgets.common.theme_widgets import ColorSwatchButton

SettingsDialog = PreferencesDialog
ColorPickerButton = ColorSwatchButton

__all__ = [
    "PreferencesDialog",
    "SettingsDialog",
    "ColorSwatchButton",
    "ColorPickerButton",
]
