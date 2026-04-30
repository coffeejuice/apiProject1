from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document.block import Block
    from app.models.document.document import Document


class DocumentOperation(Base):
    """Parsed/effective technological operation generated from document blocks."""

    __tablename__ = "document_operations"

    document_operation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_blocks.block_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    operation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_order_in_block: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source_block_type_id: Mapped[str] = mapped_column(String(100), nullable=False)

    operation_template_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    operation_kind: Mapped[str] = mapped_column(String(63), nullable=False, default="generic", server_default="generic")
    label_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)

    document_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    heating_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    deformation_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    furnace_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    operation_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    effective_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    template_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    source_text_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, default=None)
    parse_status: Mapped[str] = mapped_column(String(31), nullable=False, default="valid", server_default="valid")
    parse_errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    parse_warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    document: Mapped["Document"] = relationship("Document")
    source_block: Mapped["Block"] = relationship("Block", foreign_keys=[source_block_id])

    __table_args__ = (
        UniqueConstraint("document_id", "operation_order", name="uq_document_operations_document_order"),
        UniqueConstraint("source_block_id", "operation_order_in_block", name="uq_document_operations_source_block_order"),
    )
