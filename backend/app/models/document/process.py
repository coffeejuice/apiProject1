from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, Enum as SQLEnum, BigInteger, SmallInteger, Numeric, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document.block import Block
    from app.models.document.revision import Revision
    from app.models.server import Server
    from app.models.library import Material
import uuid
import enum
from app.database import Base

class Role(enum.Enum):
    owner = "owner"
    editor = "editor"
    viewer = "viewer"

class Status(enum.Enum):
    empty = "empty"
    error = "error"
    ok = "ok"
    ok_not_editable = "ok_not_editable"

class SimulationStatus(enum.Enum):
    stop = "stop"
    run = "run"
    pause = "pause"
    error = "error"
    done = "done"

class Process(Base):
    __tablename__ = "processes"

    process_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.user_id", name="fk_process_user_id_users_user_id", ondelete="SET DEFAULT"), default=1)
    material_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("material.material_id", name="fk_process_material_id_material_material_id", ondelete="SET DEFAULT"), default=1)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_edit_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_rev_number: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    owner: Mapped["User"] = relationship("User", back_populates="process_owner")
    blocks: Mapped[List["Block"]] = relationship("Block", back_populates="document", cascade="all, delete-orphan")
    revisions: Mapped[List["Revision"]] = relationship("Revision", back_populates="document", cascade="all, delete-orphan")
    versions: Mapped[List["ProcessVersion"]] = relationship("ProcessVersion", back_populates="process", foreign_keys="[ProcessVersion.process_id]", cascade="all, delete-orphan")
    acl: Mapped[List["ProcessACL"]] = relationship("ProcessACL", back_populates="document", cascade="all, delete-orphan")
    share_links: Mapped[List["ShareLink"]] = relationship("ShareLink", back_populates="document", cascade="all, delete-orphan")

class ProcessVersion(Base):
    __tablename__ = "process_versions"

    process_version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    process_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("processes.process_id", ondelete="RESTRICT"), nullable=True)
    parent_process_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("process_versions.process_version_id", ondelete="SET NULL"), nullable=True, default=None)

    is_editable: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)

    run_switch_status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    run_switch_is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    simulation_status: Mapped[SimulationStatus] = mapped_column(SQLEnum(SimulationStatus, name="simulation_status_enum"), nullable=False, default=SimulationStatus.stop)

    execution_order: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)
    operations_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)
    simulation_expected_duration_days: Mapped[Optional[float]] = mapped_column(Float, default=0, nullable=True)
    simulation_percent: Mapped[Optional[int]] = mapped_column(SmallInteger, default=0, nullable=True)

    simulation_server_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("servers.id", onupdate="CASCADE", ondelete="SET DEFAULT"), nullable=True, default=None)
    db_path_name: Mapped[Optional[str]] = mapped_column(String(2047), nullable=True, default=None)

    name: Mapped[str] = mapped_column(String(2047), nullable=False)
    ppt_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    pdf_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    db_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    project_dir_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_modified: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    ran_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

    from app.models.user import UserPriority
    process_priority_enum: Mapped[UserPriority] = mapped_column(SQLEnum(UserPriority, name="priority_enum"), nullable=False, default=UserPriority.normal)

    simulation_priority: Mapped[Optional[int]] = mapped_column(SmallInteger, default=5, nullable=True)
    simulation_queue_number: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)
    simulation_queue_row_number: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=None)

    process: Mapped[Optional["Process"]] = relationship("Process", back_populates="versions", foreign_keys=[process_id])
    parent_version: Mapped[Optional["ProcessVersion"]] = relationship("ProcessVersion", remote_side=[process_version_id])
    simulation_server: Mapped[Optional["Server"]] = relationship("Server", foreign_keys=[simulation_server_id])

class ProcessACL(Base):
    __tablename__ = "process_acl"

    acl_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    process_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("processes.process_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)
    role: Mapped[Role] = mapped_column(SQLEnum(Role), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Process"] = relationship("Process", back_populates="acl")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("idx_document_user", "process_id", "user_id", unique=True),
    )

class ShareLink(Base):
    __tablename__ = "share_links"

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    process_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("processes.process_id"), nullable=False)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.user_id"), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    document: Mapped["Process"] = relationship("Process", back_populates="share_links")
