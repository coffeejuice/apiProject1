from sqlalchemy import String, DateTime, ForeignKey, Index, Enum as SQLEnum, Boolean, SmallInteger, Float, BigInteger, UniqueConstraint, func, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional, TYPE_CHECKING
import enum
from app.database import Base

if TYPE_CHECKING:
    from app.models.document.process import ProcessVersion


class ServerType(enum.Enum):
    pre = "pre"
    post = "post"
    simulation = "simulation"
    sql = "sql"
    client = "client"
    file_server = "file_server"


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    type: Mapped[ServerType] = mapped_column(SQLEnum(ServerType, native_enum=False), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    dns_domain: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    ip: Mapped[str] = mapped_column(String(63), nullable=False)
    port_number: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    login_name: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    login_password: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    version: Mapped[str] = mapped_column(String(63), nullable=False)
    time_started: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    time_updated: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    time_finished: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    process_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("process_versions.process_version_id", onupdate="CASCADE", ondelete="SET DEFAULT"), nullable=True)
    projects_dir: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    local_dir: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    public_dir: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    software_root_dir: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    data_files_dies: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    data_files_materials: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    data_files_operations: Mapped[str] = mapped_column(String(2047), default="", nullable=True)
    nas: Mapped[str] = mapped_column(String(2047), default="", nullable=True)

    max_threads_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    cpu_performance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cpu_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    ram_free_size_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hdd_free_size_gb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    notify_timeout: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)
    timeout_query_missed_tasks: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)
    queue_timeout: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)
    notify_channel: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    timeout_counter: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=True)

    process_version: Mapped[Optional["ProcessVersion"]] = relationship("ProcessVersion", foreign_keys=[process_version_id])

    __table_args__ = (
        UniqueConstraint("type", "hostname", "name", name="uk_servers_1"),
    )


class PhysicalMachine(Base):
    __tablename__ = "physical_machines"

    phm_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(17), nullable=False)
    hard_drives_list: Mapped[str] = mapped_column(String(511), nullable=False)
    cpu_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    core_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    processor_architecture: Mapped[str] = mapped_column(String(63), nullable=False)
    ram_size: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(String(511), nullable=False, default="")


