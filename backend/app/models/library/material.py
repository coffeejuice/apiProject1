from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.document.document import Document
    from app.models.workflow_runtime import SimulationStep


class Material(Base):
    __tablename__ = "materials"

    material_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(1023), nullable=False)
    deform_file_name: Mapped[Optional[str]] = mapped_column(
        String(1023),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_obsolete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    classification_assignments: Mapped[list["MaterialClassificationAssignment"]] = relationship(
        "MaterialClassificationAssignment",
        back_populates="material",
        cascade="all, delete-orphan",
    )
    designations: Mapped[list["MaterialDesignation"]] = relationship(
        "MaterialDesignation",
        back_populates="material",
        cascade="all, delete-orphan",
    )
    test_records: Mapped[list["MaterialTestRecord"]] = relationship(
        "MaterialTestRecord",
        back_populates="material",
        cascade="all, delete-orphan",
    )
    versions: Mapped[list["MaterialVersion"]] = relationship(
        "MaterialVersion",
        back_populates="material",
        cascade="all, delete-orphan",
    )


class MaterialVersion(Base):
    __tablename__ = "material_versions"

    material_version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials.material_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    name_snapshot: Mapped[str] = mapped_column(String(1023), nullable=False)
    deform_file_name: Mapped[Optional[str]] = mapped_column(String(1023), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=text("now()"),
    )

    material: Mapped["Material"] = relationship("Material", back_populates="versions")
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="material_version")
    simulation_steps: Mapped[list["SimulationStep"]] = relationship(
        "SimulationStep",
        back_populates="material_version",
    )

    __table_args__ = (
        UniqueConstraint("material_id", "version_no", name="uq_material_versions_material_version_no"),
    )
