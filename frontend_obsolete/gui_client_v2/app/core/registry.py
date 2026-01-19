from typing import Dict, Type, Optional, Any
from PySide6.QtCore import QObject

class BlockRegistry:
    _mappings: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, block_type: str, qml_path: str, viewmodel_class: Type[QObject]):
        cls._mappings[block_type] = {
            "qml": qml_path,
            "viewmodel": viewmodel_class
        }

    @classmethod
    def get_qml_path(cls, block_type: str) -> str:
        return cls._mappings.get(block_type, {}).get("qml", "blocks/UnknownBlock.qml")

    @classmethod
    def create_viewmodel(cls, block_type: str, data: dict) -> Optional[QObject]:
        entry = cls._mappings.get(block_type)
        if entry:
            vm_class = entry.get("viewmodel")
            return vm_class(data)
        return None
