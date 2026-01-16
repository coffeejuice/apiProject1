from PySide6.QtCore import QObject, Property, Signal, Slot
from ..core.registry import BlockRegistry
from .cell import CellModel


class BlockViewModel(QObject):
    """
    Represents a Block (Card in C++ terminology).
    Each block contains a CellModel with multiple cells.
    """
    dataChanged = Signal()
    blockIdChanged = Signal()
    blockTypeChanged = Signal()

    def __init__(self, data: dict):
        super().__init__()
        self._data = data
        self._cell_model = CellModel(self)

        # Load cells from data if present
        cells_data = data.get("cells", [])
        if cells_data:
            self._cell_model.loadCells(cells_data)

    @Property(str, notify=blockIdChanged)
    def block_id(self):
        return str(self._data.get("block_id", ""))

    @Property(str, notify=blockTypeChanged)
    def block_type(self):
        return self._data.get("block_type", "text")

    @Property(QObject, constant=True)
    def cellModel(self):
        """Returns the CellModel containing this block's cells"""
        return self._cell_model

    @Property(str, notify=dataChanged)
    def qmlPath(self):
        return BlockRegistry.get_qml_path(self.block_type)

    @Slot(str, str)
    def addCell(self, angle="", height=""):
        """Add a new cell to this block"""
        self._cell_model.appendCell(angle, height)
        # Notify parent if needed for sync

    @Slot(int)
    def removeCell(self, index):
        """Remove cell at specified index"""
        self._cell_model.removeCell(index)

class TextBlockViewModel(BlockViewModel):
    textChanged = Signal()

    def __init__(self, data: dict):
        super().__init__(data)
        self.parent = None

    @Property(str, notify=textChanged)
    def text(self):
        return self._data.get("text", "")

    @text.setter
    def text(self, value):
        if self._data.get("text") != value:
            self._data["text"] = value
            self.textChanged.emit()
            if self.parent:
                self.parent.sync_block(self.block_id, value)

# Registering default types
BlockRegistry.register("text", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("paragraph", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("heading1", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("heading2", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("list", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("todo", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("code", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("quote", "blocks/TextBlock.qml", TextBlockViewModel)
BlockRegistry.register("divider", "blocks/TextBlock.qml", TextBlockViewModel)
