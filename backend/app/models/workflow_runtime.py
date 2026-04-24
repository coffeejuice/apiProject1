from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Double,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document.block import Block
    from app.models.document.document import DocumentVersion
    from app.models.library.die import Die, DieAssembly
    from app.models.library.library import OperationsLibrary
    from app.models.library.material import MaterialVersion
    from app.models.library.press import Press, PressMode
    from app.models.server import Server


class SimulationStepStatusEnum(enum.Enum):
    blocked = "blocked"
    queued = "queued"
    running = "running"
    finished = "finished"
    failed = "failed"
    cancelled = "cancelled"


class PostprocessingTaskStatusEnum(enum.Enum):
    queued = "queued"
    running = "running"
    finished = "finished"
    failed = "failed"
    cancelled = "cancelled"


class SimulationStep(Base):
    __tablename__ = "simulation_steps"

    simulation_step_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("document_versions.document_version_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_block_id: Mapped[Optional[Any]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_blocks.block_id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    block_type_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("document_blocks_library.type_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    block_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    library_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)

    material_version_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("material_versions.material_version_id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    press_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("presses.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    press_mode_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("press_modes.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    die_assembly_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("die_assemblies.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    top_die_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("dies.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    bottom_die_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("dies.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    left_die_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("dies.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    right_die_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("dies.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    parameter_values: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    control_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    step_specific_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    initial_geometry: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True, default=None)
    final_geometry: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True, default=None)
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    accumulated_time_start_seconds: Mapped[Optional[float]] = mapped_column(Double, nullable=True, default=None)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Double, nullable=True, default=None)
    accumulated_time_stop_seconds: Mapped[Optional[float]] = mapped_column(Double, nullable=True, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    document_version: Mapped["DocumentVersion"] = relationship("DocumentVersion")
    source_block: Mapped[Optional["Block"]] = relationship("Block", foreign_keys=[source_block_id])
    block_type: Mapped["OperationsLibrary"] = relationship("OperationsLibrary", foreign_keys=[block_type_id])
    material_version: Mapped[Optional["MaterialVersion"]] = relationship(
        "MaterialVersion",
        back_populates="simulation_steps",
    )
    press: Mapped[Optional["Press"]] = relationship("Press", foreign_keys=[press_id])
    press_mode: Mapped[Optional["PressMode"]] = relationship("PressMode", foreign_keys=[press_mode_id])
    die_assembly: Mapped[Optional["DieAssembly"]] = relationship("DieAssembly", foreign_keys=[die_assembly_id])
    top_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[top_die_id])
    bottom_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[bottom_die_id])
    left_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[left_die_id])
    right_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[right_die_id])
    status: Mapped[Optional["SimulationStepStatus"]] = relationship(
        "SimulationStepStatus",
        back_populates="simulation_step",
        cascade="all, delete-orphan",
        uselist=False,
    )
    postprocessing_tasks: Mapped[list["PostprocessingTask"]] = relationship(
        "PostprocessingTask",
        back_populates="simulation_step",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "document_version_id",
            "execution_order",
            name="uq_simulation_steps_document_version_execution_order",
        ),
    )


class SimulationStepStatus(Base):
    __tablename__ = "simulation_step_status"

    simulation_step_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_steps.simulation_step_id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[SimulationStepStatusEnum] = mapped_column(
        SQLEnum(
            SimulationStepStatusEnum,
            name="simulation_step_status_enum",
        ),
        nullable=False,
        default=SimulationStepStatusEnum.blocked,
        server_default=SimulationStepStatusEnum.blocked.value,
        index=True,
    )
    simulation_server_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("servers.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    worker_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    simulation_percent: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    simulation_expected_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Double,
        nullable=True,
        default=None,
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    runtime_artifacts: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    error_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    simulation_step: Mapped["SimulationStep"] = relationship("SimulationStep", back_populates="status")
    simulation_server: Mapped[Optional["Server"]] = relationship("Server", foreign_keys=[simulation_server_id])


class PostprocessingTask(Base):
    __tablename__ = "postprocessing_tasks"

    postprocessing_task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    simulation_step_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("simulation_steps.simulation_step_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_kind: Mapped[str] = mapped_column(
        String(63),
        nullable=False,
        default="full",
        server_default="full",
    )
    status: Mapped[PostprocessingTaskStatusEnum] = mapped_column(
        SQLEnum(
            PostprocessingTaskStatusEnum,
            name="postprocessing_task_status_enum",
        ),
        nullable=False,
        default=PostprocessingTaskStatusEnum.queued,
        server_default=PostprocessingTaskStatusEnum.queued.value,
        index=True,
    )
    postprocessing_server_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("servers.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )
    worker_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    input_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    output_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    images_dir_path: Mapped[Optional[str]] = mapped_column(String(2047), nullable=True, default=None)
    pptx_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    pdf_file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    error_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True, default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    simulation_step: Mapped["SimulationStep"] = relationship("SimulationStep", back_populates="postprocessing_tasks")
    postprocessing_server: Mapped[Optional["Server"]] = relationship("Server", foreign_keys=[postprocessing_server_id])

    __table_args__ = (
        UniqueConstraint(
            "simulation_step_id",
            "task_kind",
            name="uq_postprocessing_tasks_simulation_step_task_kind",
        ),
    )
