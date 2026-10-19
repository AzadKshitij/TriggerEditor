"""About dialog: what this is, which version, where its data lives.

The old ``about()`` opened a message box with the title of the upstream
nodeeditor sample and a link to an unrelated tutorial - boilerplate that
described the example, not this application. The dead ``qt/models/about.py``
that was meant to replace it imported a ``tagstudio`` package that does not
exist and was never instantiated.

This dialog shows the real thing: the app icon, the name, the version, the
settings location (there is no config file - the preferences live in one
INI), and the repository.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.constants import VERSION, VERSION_BRANCH
from trigger_designer.qt.preferences import preferences_path
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common.config_widgets import (
    ConfigSection,
    TextButton,
)

REPOSITORY_URL = "https://github.com/AzadKshitij/TriggerEditor"

DESCRIPTION = "Build data-processing workflows as a graph of nodes, and run them."

#: The app icon is a 256px .ico; the dialog shows it at this width.
LOGO_WIDTH = 48


class AboutDialog(QDialog):
    """The application's own About box."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Trigger Designer")
        self.setObjectName("AboutDialog")
        self.setMinimumWidth(420)
        # The dialog is opened and closed over and over; without this every
        # open leaves a window behind.
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(12)

        layout.addLayout(self._build_header())

        details = ConfigSection("Details")
        form = QFormLayout()
        form.setContentsMargins(10, 10, 10, 10)
        form.setSpacing(6)
        form.addRow("Version", QLabel(self._version_text()))
        form.addRow("Settings", QLabel(str(preferences_path())))
        form.addRow("Source", self._build_link())
        details.addLayout(form)
        layout.addWidget(details)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        close = TextButton("Close")
        close.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    @staticmethod
    def _version_text() -> str:
        branch = f" ({VERSION_BRANCH})" if VERSION_BRANCH else ""
        return f"{VERSION}{branch}"

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self._build_logo())

        text = QVBoxLayout()
        text.setSpacing(2)
        title = QLabel("Trigger Designer")
        title.setObjectName("AboutTitle")
        text.addWidget(title)
        description = QLabel(DESCRIPTION)
        description.setObjectName("AboutDescription")
        description.setWordWrap(True)
        text.addWidget(description)
        row.addLayout(text, 1)
        return row

    @staticmethod
    def _build_logo() -> QLabel:
        logo = QLabel()
        logo.setObjectName("AboutLogo")
        path = ResourceManager.get_full_path("app_icon")
        if path is not None and path.exists():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaledToWidth(
                        LOGO_WIDTH, Qt.TransformationMode.SmoothTransformation
                    )
                )
        return logo

    @staticmethod
    def _build_link() -> QLabel:
        link = QLabel(f'<a href="{REPOSITORY_URL}">{REPOSITORY_URL}</a>')
        link.setObjectName("AboutLink")
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(
            link.textInteractionFlags() | Qt.TextInteractionFlag.TextBrowserInteraction
        )
        return link
