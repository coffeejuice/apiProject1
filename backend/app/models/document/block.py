from datetime import datetime
from typing import Optional, TYPE_CHECKING
import uuid
import enum

from sqlalchemy import String, DateTime, ForeignKey, Index, Boolean, SmallInteger, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.document.document import Document


class BlockType(enum.Enum):
    document_heading = "document_heading"
    input_workpiece = "input_workpiece"


class DeformationType(enum.Enum):
    upsetting = "upsetting"
    axial_prolongation = "axial_prolongation"
    radial_prolongation = "radial_prolongation"
    full_die = "full_die"
    hot_cutting = "hot_cutting"
    cold_sawing = "cold_sawing"


class IngotSide(enum.Enum):
    top = "top"
    bottom = "bottom"


class FeedDirection(enum.Enum):
    left = "Left"
    right = "Right"
    alternating = "Alternating"


class Block(Base):
    __tablename__ = "document_blocks"

    block_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False
    )
    previous_block_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_blocks.block_id", ondelete="SET NULL"), nullable=True, default=None
    )
    next_block_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_blocks.block_id", ondelete="SET NULL"), nullable=True, default=None
    )
    block_type_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    props: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # System block metadata (kept for handler-based blocks)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_removable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fixed_position: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)

    document: Mapped["Document"] = relationship("Document", back_populates="blocks", foreign_keys=[document_id])

    @property
    def block_type(self) -> str:
        return self.block_type_id

    @block_type.setter
    def block_type(self, value: object) -> None:
        if isinstance(value, BlockType):
            self.block_type_id = value.value
        else:
            self.block_type_id = str(value)

    __table_args__ = (
        Index("idx_document_prev_block", "document_id", "previous_block_id"),
        Index("idx_document_next_block", "document_id", "next_block_id"),
    )
