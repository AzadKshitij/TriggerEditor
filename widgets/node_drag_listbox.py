from turtle import width
from qtpy.QtGui import QPixmap, QIcon, QDrag
from qtpy.QtCore import QSize, Qt, QByteArray, QDataStream, QMimeData, QIODevice, QPoint
from qtpy.QtWidgets import QListWidget, QAbstractItemView, QListWidgetItem, QWidget, QVBoxLayout, QLabel

from trigger_conf import CALC_NODES, get_class_from_opcode, LISTBOX_MIMETYPE
from nodeeditor.utils import dumpException


class QTRDragListbox(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.setFlow(QListWidget.LeftToRight)

    def initUI(self):
        # init
        self.setIconSize(QSize(32, 32))
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)

        self.addMyItems()

    def addMyItems(self):
        keys = list(CALC_NODES.keys())
        keys.sort()
        for key in keys:
            node = get_class_from_opcode(key)
            self.addMyItem(node.op_title, node.icon, node.op_code)

    # def addMyItem(self, name, icon=None, op_code=0):
    #     # can be (icon, text, parent, <int>type)
    #     item = QListWidgetItem(name, self)
    #     # item.setTextAlignment(Qt.AlignmentFlag.AlignBottom)
    #     item_widget = ListWidgetItemWidget(name, icon)
    #     item.setSizeHint(item_widget.sizeHint())
    #     self.addItem(item)

    #     pixmap = QPixmap(icon if icon is not None else ".")
    #     item.setIcon(QIcon(pixmap))
    #     item.setSizeHint(QSize(32, 32))

    #     item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable |
    #                   Qt.ItemIsDragEnabled)

    #     # setup data
    #     item.setData(Qt.UserRole, pixmap)
    #     item.setData(Qt.UserRole + 1, op_code)

    def addMyItem(self, name, icon=None, op_code=0):
        item = QListWidgetItem(self)
        item_widget = ListWidgetItemWidget(name, icon)
        item.setSizeHint(item_widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, item_widget)

        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable |
                      Qt.ItemIsDragEnabled)

        # setup data
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
            dataStream.writeQString(item.text())

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
    def __init__(self, name, icon=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(QSize(64, 64))
        self.text_label = QLabel(name, self)
        self.icon_label.setFixedHeight(32)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if icon:
            pixmap = QPixmap(icon)
            self.icon_label.setPixmap(pixmap)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.setLayout(layout)
