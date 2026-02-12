"""Base class for block type handlers"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from uuid import UUID


class BlockTypeHandler(ABC):
    """
    Base class for block type handlers.
    Each block type implements this to define its behavior.
    """

    @property
    @abstractmethod
    def block_type_name(self) -> str:
        """Return the block type name (must match BlockType enum)"""
        pass

    @property
    def is_system_block(self) -> bool:
        """Is this a system block that cannot be removed?"""
        return False

    @property
    def is_removable(self) -> bool:
        """Can this block be deleted by the user?"""
        return True

    @property
    def fixed_position(self) -> Optional[int]:
        """
        Fixed position in document (0-based).
        None means the block can be reordered freely.
        """
        return None

    @property
    def allow_multiple_instances(self) -> bool:
        """Can multiple instances of this block exist in one document?"""
        return True

    @abstractmethod
    def get_default_props(self) -> Dict[str, Any]:
        """Return default props for a new block of this type"""
        pass

    @abstractmethod
    def validate_props(self, props: Dict[str, Any]) -> bool:
        """Validate block props. Return True if valid."""
        pass

    def on_create(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> None:
        """
        Called when a block of this type is created.
        Override to perform custom initialization.
        """
        pass

    def on_update(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> None:
        """
        Called when a block of this type is updated.
        Override to perform custom logic (e.g., update related tables).
        """
        pass

    def on_delete(self, db: Session, block_id: UUID, document_id: int) -> None:
        """
        Called when a block of this type is deleted.
        Override to perform cleanup.
        """
        pass

    def serialize_for_frontend(self, db: Session, block_id: UUID, document_id: int, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize block data for frontend.
        Override to include data from related tables.
        Default implementation returns just the props.
        """
        return props

    def get_editable_fields(self) -> List[str]:
        """
        Return list of editable field names in props.
        Used for frontend validation and UI generation.
        """
        return []

    def get_field_limits(self) -> Dict[str, int]:
        """
        Return per-field max string lengths for frontend input limiting.
        Keys are dot-paths in props (for example, "name" or "version.name").
        """
        return {}
