from qtpy.QtGui import (
    QPixmap,
    QIcon,
    QDrag,
    QPainter,
    QColor,
    QFont,
    QCursor,
    QMouseEvent,
    QPainterPath,
)
from qtpy.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from qtpy.QtWidgets import (
    QListWidget,
    QAbstractItemView,
    QListWidgetItem,
    QWidget,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QHBoxLayout,
    QGridLayout,
    QFrame,
)

from nodeeditor.utils import dumpException

from typing import Any, Optional

from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.core.node_configuration import (
    NodeTypes,
    get_class_from_opcode,
    LISTBOX_MIMETYPE,
    NODE_REGISTRIES,
)


class QTRDragListbox(QListWidget):
    def __init__(
        self, parent: Optional[QWidget] = None, node_type: Optional[NodeTypes] = None
    ) -> None:
        super().__init__(parent)
        self.node_type = node_type
        self.horizontal_spacing = 15

        self.initUI()
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListWidget.ResizeMode.Fixed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def initUI(self) -> None:
        # init
        self.setIconSize(QSize(32, 32))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self.addMyItems()

    # def addMyItems(self) -> None:

    #     current_node_type = check_node_type(self.node_type)

    #     keys = list(current_node_type.keys())
    #     keys.sort()
    #     for key in keys:
    #         node: TriggerNode = get_class_from_opcode(key, self.node_type)
    #         self.addMyItem(node.node_title, node.icon, node.node_code)

    def addMyItems(self) -> None:
        """Add items to the listbox based on node type"""
        if not self.node_type:
            return

        # Get registry for this node type
        node_registry = NODE_REGISTRIES[self.node_type]

        # Sort keys for consistent ordering
        keys = sorted(node_registry.keys())

        for key in keys:
            node_class = node_registry[key]
            self.addMyItem(
                name=node_class.node_title, icon=node_class.icon, node_code=key
            )

    def addMyItem(self, name: str = "", icon: str = "", node_code: int = 0) -> None:
        item = QListWidgetItem(self)
        item_widget = ListWidgetItemWidget(name, icon, self.node_type)
        item.setSizeHint(item_widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, item_widget)

        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)

        # spacer = QListWidgetItem(self)
        # spacer.setSizeHint(QSize(self.horizontal_spacing, 0))
        # spacer.setFlags(spacer.flags() & ~spacer.flags())
        # # spacer.setSizeHint(card.sizeHint().expandedTo(spacer.sizeHint()))
        # # spacer.setSizeHint(spacer.sizeHint().grownBy(horizontal_spacing))
        # self.addItem(spacer)

        # setup data
        # item.setData(Qt.UserRole, pixmap)
        item.setData(Qt.UserRole + 1, node_code)

    def startDrag(self, *args: list[Any], **kwargs: dict[Any, Any]) -> None:
        try:
            # item = self.currentItem()
            # node_code = item.data(Qt.UserRole + 1)

            # pixmap = QPixmap(item.data(Qt.UserRole))

            item = self.currentItem()
            node_code = item.data(Qt.UserRole + 1)
            item_widget = self.itemWidget(item)
            pixmap = item_widget.icon_label.pixmap()

            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream << pixmap
            dataStream.writeInt(node_code)
            dataStream.writeQString(self.node_type)
            # dataStream.writeQString(item.text())

            mimeData = QMimeData()
            mimeData.setData(LISTBOX_MIMETYPE, itemData)

            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            drag.setPixmap(pixmap)

            drag.exec_(Qt.MoveAction)

        except Exception as e:
            dumpException(e)


class ListWidgetItemWidget(QWidget):
    def __init__(
        self,
        name: str,
        icon: str = "",
        node_type: Optional[str] = "DEFAULT",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setObjectName("listItemWidget")
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        # layout.setAlignment(Qt.AlignmentFlag.AlignJustify)

        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rsm = ResourceManager()
        pixmap = self.rsm.get(icon)

        if pixmap:
            # pixmap.setDevicePixelRatio(2)  # High-DPI fix
            pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.FastTransformation)
            # rounded = self.create_rounded_icon(pixmap, radius=15)
            rounded = self.create_rounded_pixmap(pixmap, radius=12)
            self.icon_label.setPixmap(rounded)
            self.icon_label.setFixedSize(QSize(48, 48))

        self.text_label = QLabel(name, self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setFont(QFont("Arial", 8))
        self.text_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.text_label.setMinimumWidth(self.icon_label.width())

        # self.text_label.setFixedHeight(20)

        layout.addWidget(self.icon_label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        # icon_layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label, 1, 0, Qt.AlignmentFlag.AlignCenter)

        self.setLayout(layout)
        # Set fixed size for the widget
        # self.setMinimumHeight(100)
        # self.setMinimumHeight(100)
        # self.setFixedHeight(100)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def create_rounded_icon(self, pixmap: QPixmap, radius: int) -> QPixmap:
        """Create a new pixmap with rounded corners by clipping the original image."""
        # Create transparent pixmap with same size
        result = QPixmap(pixmap.size())
        result.fill(Qt.GlobalColor.transparent)

        # Create painter with antialiasing
        painter = QPainter(result)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        # Create rounded rectangle path
        path = QPainterPath()
        path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)

        # Set clipping path and draw original pixmap
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return result

    # Add this helper method to your class to create rounded pixmaps
    def create_rounded_pixmap(self, pixmap: QPixmap, radius: int) -> QPixmap:
        """Create a pixmap with rounded corners."""
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)

        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return rounded
