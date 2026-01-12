from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, Boolean, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum
from app.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    devices = relationship("Device", back_populates="user")
    documents = relationship("Document", back_populates="owner")

class Device(Base):
    __tablename__ = "devices"

    device_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    device_name = Column(String(100))
    last_sync = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="devices")

class Document(Base):
    __tablename__ = "documents"

    document_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    current_rev_number = Column(Integer, default=0)

    owner = relationship("User", back_populates="documents")
    blocks = relationship("Block", back_populates="document", cascade="all, delete-orphan")
    revisions = relationship("Revision", back_populates="document", cascade="all, delete-orphan")
    acl = relationship("DocumentACL", back_populates="document", cascade="all, delete-orphan")
    share_links = relationship("ShareLink", back_populates="document", cascade="all, delete-orphan")

class BlockType(enum.Enum):
    paragraph = "paragraph"
    heading1 = "heading1"
    heading2 = "heading2"
    list = "list"
    todo = "todo"
    code = "code"
    quote = "quote"
    divider = "divider"

class Block(Base):
    __tablename__ = "blocks"

    block_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False)
    parent_block_id = Column(UUID(as_uuid=True), nullable=True)
    order_key = Column(String(100), nullable=False)
    block_type = Column(SQLEnum(BlockType), nullable=False)
    text = Column(Text, default="")
    props = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="blocks")

    __table_args__ = (
        Index("idx_document_parent", "document_id", "parent_block_id"),
        Index("idx_document_order", "document_id", "order_key"),
    )

class Revision(Base):
    __tablename__ = "revisions"

    revision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False)
    rev_number = Column(Integer, nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.device_id"), nullable=False)
    client_batch_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    document = relationship("Document", back_populates="revisions")
    ops = relationship("Operation", back_populates="revision", cascade="all, delete-orphan")
    snapshot = relationship("RevisionSnapshot", back_populates="revision", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_document_rev", "document_id", "rev_number"),
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

    op_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id = Column(UUID(as_uuid=True), ForeignKey("revisions.revision_id"), nullable=False)
    op_type = Column(SQLEnum(OperationType), nullable=False)
    block_id = Column(UUID(as_uuid=True), nullable=False)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    revision = relationship("Revision", back_populates="ops")

class RevisionSnapshot(Base):
    __tablename__ = "revision_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    revision_id = Column(UUID(as_uuid=True), ForeignKey("revisions.revision_id"), nullable=False, unique=True)
    blocks_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    revision = relationship("Revision", back_populates="snapshot")

class Role(enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"

class DocumentACL(Base):
    __tablename__ = "document_acl"

    acl_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    role = Column(SQLEnum(Role), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="acl")
    user = relationship("User")

    __table_args__ = (
        Index("idx_document_user", "document_id", "user_id", unique=True),
    )

class ShareLink(Base):
    __tablename__ = "share_links"

    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.document_id"), nullable=False)
    token = Column(String(100), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    expires_at = Column(DateTime, nullable=True)

    document = relationship("Document", back_populates="share_links")
