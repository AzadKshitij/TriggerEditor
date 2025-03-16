from turtle import width
from qtpy.QtGui import QPixmap, QIcon, QDrag, QPainter, QColor, QFont, QCursor, QMouseEvent
from qtpy.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from qtpy.QtWidgets import (
    QListWidget, QAbstractItemView, QListWidgetItem, QWidget, QVBoxLayout, QLabel, QSizePolicy, QHBoxLayout, QGridLayout, QFrame)

from trigger_conf import check_node_type, get_class_from_opcode, LISTBOX_MIMETYPE
from nodeeditor.utils import dumpException

from themes.theme import Theme

theme = Theme()


class QTRDragListbox(QListWidget):
    def __init__(self, parent=None, node_type=None):
        super().__init__(parent)
        self.node_type = node_type
        self.horizontal_spacing = 15

        self.initUI()
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListWidget.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListWidget.ResizeMode.Fixed)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def initUI(self):
        # init
        self.setIconSize(QSize(32, 32))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self.addMyItems()

    def addMyItems(self):
        current_node_type = check_node_type(self.node_type)

        keys = list(current_node_type.keys())
        print(f"node_type: {self.node_type}")
        keys.sort()
        for key in keys:
            node = get_class_from_opcode(key, self.node_type)
            self.addMyItem(node.op_title, node.icon, node.op_code)

    def addMyItem(self, name, icon=None, op_code=0):
        item = QListWidgetItem(self)
        item_widget = ListWidgetItemWidget(name, icon, self.node_type)
        item.setSizeHint(item_widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, item_widget)

        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable |
                      Qt.ItemIsDragEnabled)

        # spacer = QListWidgetItem(self)
        # spacer.setSizeHint(QSize(self.horizontal_spacing, 0))
        # spacer.setFlags(spacer.flags() & ~spacer.flags())
        # # spacer.setSizeHint(card.sizeHint().expandedTo(spacer.sizeHint()))
        # # spacer.setSizeHint(spacer.sizeHint().grownBy(horizontal_spacing))
        # self.addItem(spacer)

        # setup data
        # item.setData(Qt.UserRole, pixmap)
        item.setData(Qt.UserRole + 1, op_code)

    def startDrag(self, *args, **kwargs):
        try:
            # item = self.currentItem()
            # op_code = item.data(Qt.UserRole + 1)

            # pixmap = QPixmap(item.data(Qt.UserRole))

            item = self.currentItem()
            op_code = item.data(Qt.UserRole + 1)
            item_widget = self.itemWidget(item)
            pixmap = item_widget.icon_label.pixmap()

            itemData = QByteArray()
            dataStream = QDataStream(itemData, QIODevice.WriteOnly)
            dataStream << pixmap
            dataStream.writeInt(op_code)
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
    def __init__(self, name, icon=None, node_type="DEFAULT", parent=None):
        super().__init__(parent)

        layout = QGridLayout(self)
        layout.setObjectName("listItemWidget")
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        # layout.setAlignment(Qt.AlignmentFlag.AlignJustify)

        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if icon:
            # .scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pixmap = QPixmap(icon)
            # pixmap.setDevicePixelRatio(2)  # High-DPI fix
            pixmap = pixmap.scaled(
                48, 48, Qt.KeepAspectRatio, Qt.FastTransformation)
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setFixedSize(QSize(48, 48))

        self.text_label = QLabel(name, self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setFont(QFont("Arial", 8))
        self.text_label.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Fixed)  # ✅ Correct usage
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
