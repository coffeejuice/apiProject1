from sqlalchemy import String, Integer, JSON, DateTime, ForeignKey, Index, Enum as SQLEnum, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional
import uuid
import enum
from app.database import Base

class Revision(Base):
    __tablename__ = "revisions"

    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    process_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("documents.process_id"), nullable=False)
    rev_number: Mapped[int] = mapped_column(Integer, nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.device_id"), nullable=False)
    client_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.user_id"), nullable=False)

    document: Mapped["Process"] = relationship("Process", back_populates="revisions")
    ops: Mapped[List["Operation"]] = relationship("Operation", back_populates="revision", cascade="all, delete-orphan")
    snapshot: Mapped[Optional["RevisionSnapshot"]] = relationship("RevisionSnapshot", back_populates="revision", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_document_rev", "process_id", "rev_number"),
        Index("idx_device_batch", "device_id", "client_batch_id"),
    )

class OperationType(enum.Enum):
    insert_block = "insert_block"
    delete_block = "delete_block"
    move_block = "move_block"
    update_text = "update_text"
    update_props = "update_props"

class Operation(Base):
    __tablename__ = "ops"

    op_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("revisions.revision_id"), nullable=False)
    op_type: Mapped[OperationType] = mapped_column(SQLEnum(OperationType), nullable=False)
    block_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    revision: Mapped["Revision"] = relationship("Revision", back_populates="ops")

class RevisionSnapshot(Base):
    __tablename__ = "revision_snapshots"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("revisions.revision_id"), nullable=False, unique=True)
    blocks_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    revision: Mapped["Revision"] = relationship("Revision", back_populates="snapshot")
