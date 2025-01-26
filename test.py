import sys
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMainWindow, QDockWidget, QTextEdit
from qtpy.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton
import sys
from qtpy.QtWidgets import QApplication, QMainWindow, QDockWidget, QTextEdit, QVBoxLayout, QWidget, QLineEdit, QPushButton, QTableView, QCheckBox, QListWidget, QListWidgetItem
from qtpy.QtCore import Qt
import pandas as pd
from qtpy.QtCore import QAbstractTableModel


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

        line_edit = QLineEdit(self.dock_widget)
        self.dock_layout.addWidget(line_edit)

        button = QPushButton("Submit", self.dock_widget)
        self.dock_layout.addWidget(button)

        table_view = QTableView(self.dock_widget)
        data = pd.DataFrame({
            'Column 1': ['A', 'B', 'C'],
            'Column 2': [1, 2, 3]
        })
        model = PandasModel(data)
        table_view.setModel(model)
        self.dock_layout.addWidget(table_view)

    def on_button2_clicked(self):
        self.clear_dock()

        list_widget = QListWidget(self.dock_widget)
        for i in range(5):
            item = QListWidgetItem(f"Option {i+1}")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            list_widget.addItem(item)
        self.dock_layout.addWidget(list_widget)

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
