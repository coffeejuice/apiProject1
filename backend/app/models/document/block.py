from sqlalchemy import String, Text, JSON, DateTime, ForeignKey, Index, Enum as SQLEnum, Boolean, SmallInteger, BigInteger
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
import uuid
import enum
from app.database import Base

class BlockType(enum.Enum):
    # Old block types (keep for backward compatibility during migration)
    paragraph = "paragraph"
    heading1 = "heading1"
    heading2 = "heading2"
    list = "list"
    todo = "todo"
    code = "code"
    quote = "quote"
    divider = "divider"

    # System blocks (non-removable, auto-created)
    process_heading = "process_heading"
    input_workpiece = "input_workpiece"

class DeformationType(enum.Enum):
    """'upsetting', 'axial_prolongation', 'radial_prolongation', 'full_die', 'hot_cutting', 'cold_sawing'"""
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
    left = "Left"  # -X direction
    right = "Right"  # +X direction
    alternating = "Alternating"  # -X first, then reverse


class Block(Base):
    __tablename__ = "blocks"

    block_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    process_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("processes.process_id"), nullable=False)
    parent_block_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    order_key: Mapped[str] = mapped_column(String(100), nullable=False)
    block_type: Mapped[BlockType] = mapped_column(SQLEnum(BlockType), nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    props: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # System block metadata
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_removable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fixed_position: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    document: Mapped["Process"] = relationship("Process", back_populates="blocks")

    __table_args__ = (
        Index("idx_document_parent", "process_id", "parent_block_id"),
        Index("idx_document_order", "process_id", "order_key"),
    )


