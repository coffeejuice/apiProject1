from PySide6.QtCore import QObject, Property, Signal, QAbstractListModel, QModelIndex, Qt
from typing import List, Dict


class CellModel(QAbstractListModel):
    """
    Python equivalent of C++ CellModel.
    Manages a list of cells within a block/card.
    """

    AngleValueRole = Qt.UserRole + 1
    HeightValueRole = Qt.UserRole + 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cells: List[Dict[str, str]] = []

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._cells)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._cells):
            return None

        cell = self._cells[index.row()]

        if role == self.AngleValueRole:
            return cell.get("angle", "")
        elif role == self.HeightValueRole:
            return cell.get("height", "")

        return None

    def roleNames(self):
        return {
            self.AngleValueRole: b"angleValue",
            self.HeightValueRole: b"heightValue"
        }

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or index.row() >= len(self._cells):
            return False

        cell = self._cells[index.row()]

        if role == self.AngleValueRole:
            cell["angle"] = str(value)
            self.dataChanged.emit(index, index, [role])
            return True
        elif role == self.HeightValueRole:
            cell["height"] = str(value)
            self.dataChanged.emit(index, index, [role])
            return True

        return False

    # Helper methods for cell management
    def appendCell(self, angle="", height=""):
        """Add a new cell to the end of the list"""
        row = len(self._cells)
        self.beginInsertRows(QModelIndex(), row, row)
        self._cells.append({"angle": angle, "height": height})
        self.endInsertRows()

    def removeCell(self, row):
        """Remove cell at specified row"""
        if 0 <= row < len(self._cells):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._cells.pop(row)
            self.endRemoveRows()

    def loadCells(self, cells_data: List[Dict[str, str]]):
        """Load cells from data"""
        self.beginResetModel()
        self._cells = [{"angle": c.get("angle", ""), "height": c.get("height", "")} for c in cells_data]
        self.endResetModel()

    def getCellsData(self):
        """Export cells data"""
        return self._cells.copy()
