from qtpy.QtCore import QAbstractTableModel, Qt
from qtpy.QtWidgets import QWidget
from typing import Optional


class PandasModel(QAbstractTableModel):
    def __init__(self, data) -> None:
        super(PandasModel, self).__init__()
        self._data = data

    def rowCount(self, parent: Optional[QWidget] = None):
        return self._data.shape[0]

    def columnCount(self, parent: Optional[QWidget] = None):
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
