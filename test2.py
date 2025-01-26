from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QDockWidget, QVBoxLayout, QWidget
import sys
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QTableView, QListWidget, QListWidgetItem
import pandas as pd
from qtpy.QtCore import QAbstractTableModel, Qt


class CustomWidget(QWidget):
    def __init__(self, parent=None):
        super(CustomWidget, self).__init__(parent)

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.label = QLabel("Hello, this is a custom widget!", self)
        layout.addWidget(self.label)

        self.button1 = QPushButton("Button 1", self)
        layout.addWidget(self.button1)

        self.button2 = QPushButton("Button 2", self)
        layout.addWidget(self.button2)

        self.setLayout(layout)


class PandasModel(QAbstractTableModel):
    def __init__(self, data):
        super(PandasModel, self).__init__()
        self._data = data

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        return str(self._data.iloc[index.row(), index.column()])

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return self._data.columns[section]
        return None


def create_widgets_for_button1(parent):
    line_edit = QLineEdit(parent)
    button = QPushButton("Submit", parent)
    table_view = QTableView(parent)
    data = pd.DataFrame({
        'Column 1': ['A', 'B', 'C'],
        'Column 2': [1, 2, 3]
    })
    model = PandasModel(data)
    table_view.setModel(model)
    return [line_edit, button, table_view]


def create_widgets_for_button2(parent):
    list_widget = QListWidget(parent)
    for i in range(5):
        item = QListWidgetItem(f"Option {i+1}")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        list_widget.addItem(item)
    return [list_widget]


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.initUI()

    def initUI(self):
        self.setWindowTitle("QtPy Custom Widget Example")

        custom_widget = CustomWidget(self)
        self.setCentralWidget(custom_widget)

        self.createDockWidget()

        custom_widget.button1.clicked.connect(self.on_button1_clicked)
        custom_widget.button2.clicked.connect(self.on_button2_clicked)

        self.resize(600, 400)

    def createDockWidget(self):
        self.dock = QDockWidget("Sidebar", self)
        self.dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.dock_widget = QWidget()
        self.dock_layout = QVBoxLayout()
        self.dock_widget.setLayout(self.dock_layout)

        self.dock.setWidget(self.dock_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

    def on_button1_clicked(self):
        self.clear_dock()
        widgets = create_widgets_for_button1(self.dock_widget)
        for widget in widgets:
            self.dock_layout.addWidget(widget)

    def on_button2_clicked(self):
        self.clear_dock()
        widgets = create_widgets_for_button2(self.dock_widget)
        for widget in widgets:
            self.dock_layout.addWidget(widget)

    def clear_dock(self):
        for i in reversed(range(self.dock_layout.count())):
            widget = self.dock_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
