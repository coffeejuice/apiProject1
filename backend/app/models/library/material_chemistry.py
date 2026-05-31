from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PublicationCatalog(Base):
    __tablename__ = "publications_catalog"

    publication_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(63), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    publisher_or_journal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issue_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(2047), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(1023), nullable=True)
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

    material_test_records: Mapped[list["MaterialTestRecord"]] = relationship(
        "MaterialTestRecord",
        back_populates="publication",
    )


class MaterialDesignationStandardChemistry(Base):
    __tablename__ = "materials_designations_standard_chemistry"
    __table_args__ = (
        UniqueConstraint(
            "designation_id",
            "element_symbol",
            name="uq_mat_des_std_chem_desig_elem",
        ),
    )

    standard_chemistry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    designation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials_designations.designation_id", ondelete="CASCADE"),
        nullable=False,
    )
    element_symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    min_wt_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_wt_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_balance: Mapped[bool] = mapped_column(
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

    designation: Mapped["MaterialDesignation"] = relationship(
        "MaterialDesignation",
        back_populates="standard_chemistry_rows",
    )


class MaterialTestRecord(Base):
    __tablename__ = "materials_test_records"

    test_record_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials.material_id", ondelete="CASCADE"),
        nullable=False,
    )
    designation_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("materials_designations.designation_id", ondelete="SET NULL"),
        nullable=True,
    )
    publication_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("publications_catalog.publication_id", ondelete="SET NULL"),
        nullable=True,
    )
    heat_number: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    batch_number: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    sample_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    test_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
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
        back_populates="test_records",
    )
    designation: Mapped[Optional["MaterialDesignation"]] = relationship(
        "MaterialDesignation",
        back_populates="test_records",
    )
    publication: Mapped[Optional["PublicationCatalog"]] = relationship(
        "PublicationCatalog",
        back_populates="material_test_records",
    )
    chemistry_results: Mapped[list["MaterialChemistryTestResult"]] = relationship(
        "MaterialChemistryTestResult",
        back_populates="test_record",
        cascade="all, delete-orphan",
    )
    property_tables: Mapped[list["MaterialPropertyTable"]] = relationship(
        "MaterialPropertyTable",
        back_populates="test_record",
        cascade="all, delete-orphan",
    )


class MaterialChemistryTestResult(Base):
    __tablename__ = "materials_chemistry_tests_results"

    test_record_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials_test_records.test_record_id", ondelete="CASCADE"),
        primary_key=True,
    )
    element_symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    actual_wt_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    test_record: Mapped["MaterialTestRecord"] = relationship(
        "MaterialTestRecord",
        back_populates="chemistry_results",
    )
