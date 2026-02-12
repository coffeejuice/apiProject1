from sqlalchemy import String, DateTime, ForeignKey, SmallInteger, Integer, Boolean, BigInteger, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
import uuid
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.document.document import Document, DocumentEditSession
    from app.models.project import Project


class UserPriority(enum.Enum):
    low = "Low"
    normal = "Normal"
    high = "High"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hashed: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    signal_clear_token: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    supervisor_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    full_name: Mapped[Optional[str]] = mapped_column(String(511), nullable=True, default=None)
    language_code: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, default="en")
    user_settings: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    user_priority_enum: Mapped[UserPriority] = mapped_column(SQLEnum(UserPriority, name="priority_enum"), nullable=False, default=UserPriority.normal)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    devices: Mapped[List["Device"]] = relationship("Device", back_populates="user")
    project_owner: Mapped[List["Project"]] = relationship(
        "Project", back_populates="owner", foreign_keys="[Project.user_id]"
    )
    document_editor: Mapped[List["Document"]] = relationship(
        "Document", back_populates="editor", foreign_keys="[Document.editor_user_id]"
    )
    document_edit_sessions: Mapped[List["DocumentEditSession"]] = relationship(
        "DocumentEditSession",
        back_populates="editor",
        foreign_keys="[DocumentEditSession.editor_user_id]",
    )


class Device(Base):
    __tablename__ = "devices"

    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)
    device_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_sync: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="devices")
