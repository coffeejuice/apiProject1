from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StandardGeographicLevel(StrEnum):
    INTERNATIONAL = "international"
    REGIONAL = "regional"
    NATIONAL = "national"
    PRIVATE = "private"


class MaterialStandardCatalog(Base):
    __tablename__ = "material_standards_catalog"

    standard_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    predecessor_standard_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("material_standards_catalog.standard_id", ondelete="SET NULL"),
        nullable=True,
    )
    issue_organization: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    issue_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    geographic_level: Mapped[Optional[StandardGeographicLevel]] = mapped_column(
        SQLEnum(
            StandardGeographicLevel,
            name="material_standard_geographic_level_enum",
            native_enum=False,
        ),
        nullable=True,
    )
    country_or_region: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    title: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    standard_number: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(2047), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(1023), nullable=True)
    is_obsolete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
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
        onupdate=func.now(),
        server_default=func.now(),
    )

    predecessor_standard: Mapped[Optional["MaterialStandardCatalog"]] = relationship(
        "MaterialStandardCatalog",
        remote_side="MaterialStandardCatalog.standard_id",
        back_populates="successor_standards",
    )
    successor_standards: Mapped[list["MaterialStandardCatalog"]] = relationship(
        "MaterialStandardCatalog",
        back_populates="predecessor_standard",
    )
    designations: Mapped[list["MaterialDesignation"]] = relationship(
        "MaterialDesignation",
        back_populates="standard",
    )


class MaterialDesignation(Base):
    __tablename__ = "materials_designations"

    designation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation: Mapped[str] = mapped_column(String(255), nullable=False)
    material_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials.material_id", ondelete="CASCADE"),
        nullable=False,
    )
    standard_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("material_standards_catalog.standard_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_main_designation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_obsolete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
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
        onupdate=func.now(),
        server_default=func.now(),
    )

    material: Mapped["Material"] = relationship(
        "Material",
        back_populates="designations",
    )
    standard: Mapped[Optional["MaterialStandardCatalog"]] = relationship(
        "MaterialStandardCatalog",
        back_populates="designations",
    )
    standard_chemistry_rows: Mapped[list["MaterialDesignationStandardChemistry"]] = relationship(
        "MaterialDesignationStandardChemistry",
        back_populates="designation",
        cascade="all, delete-orphan",
    )
    test_records: Mapped[list["MaterialTestRecord"]] = relationship(
        "MaterialTestRecord",
        back_populates="designation",
    )
