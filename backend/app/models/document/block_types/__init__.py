"""Block type registry"""
from typing import Dict, Optional
from .base import BlockTypeHandler


class BlockTypeRegistry:
    """Registry for block type handlers"""

    def __init__(self):
        self._handlers: Dict[str, BlockTypeHandler] = {}

    def register(self, handler: BlockTypeHandler) -> None:
        """Register a block type handler"""
        self._handlers[handler.block_type_name] = handler

    def get(self, block_type: str) -> Optional[BlockTypeHandler]:
        """Get handler for a block type"""
        return self._handlers.get(block_type)

    def get_all(self) -> Dict[str, BlockTypeHandler]:
        """Get all registered handlers"""
        return self._handlers.copy()

    def get_system_blocks(self) -> Dict[str, BlockTypeHandler]:
        """Get all system block handlers"""
        return {
            name: handler
            for name, handler in self._handlers.items()
            if handler.is_system_block
        }


# Global registry instance
_registry = BlockTypeRegistry()


def register_block_type(handler: BlockTypeHandler) -> None:
    """Register a block type handler"""
    _registry.register(handler)


def get_block_type_handler(block_type: str) -> Optional[BlockTypeHandler]:
    """Get handler for a block type"""
    _ensure_handlers_registered()
    return _registry.get(block_type)


def get_all_handlers() -> Dict[str, BlockTypeHandler]:
    """Get all registered handlers"""
    _ensure_handlers_registered()
    return _registry.get_all()


def get_system_block_handlers() -> Dict[str, BlockTypeHandler]:
    """Get all system block handlers"""
    _ensure_handlers_registered()
    return _registry.get_system_blocks()


def _ensure_handlers_registered():
    """Lazy initialization of handlers to avoid circular imports"""
    if len(_registry.get_all()) == 0:
        from .document_heading import DocumentHeadingHandler
        from .input_workpiece import InputWorkpieceHandler

        register_block_type(DocumentHeadingHandler())
        register_block_type(InputWorkpieceHandler())


# Call this function before using handlers
def init_block_types():
    """Initialize block type handlers"""
    _ensure_handlers_registered()
