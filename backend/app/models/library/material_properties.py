from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialPropertyTable(Base):
    __tablename__ = "materials_property_tables"

    table_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_record_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials_test_records.test_record_id", ondelete="CASCADE"),
        nullable=False,
    )
    property_type: Mapped[str] = mapped_column(String(63), nullable=False)
    representation_kind: Mapped[str] = mapped_column(
        String(63),
        nullable=False,
        default="curve_2d",
        server_default=text("'curve_2d'"),
    )
    replicate_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    conditions: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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

    test_record: Mapped["MaterialTestRecord"] = relationship(
        "MaterialTestRecord",
        back_populates="property_tables",
    )
    columns: Mapped[list["MaterialPropertyTableColumn"]] = relationship(
        "MaterialPropertyTableColumn",
        back_populates="property_table",
        cascade="all, delete-orphan",
    )


class MaterialPropertyTableColumn(Base):
    __tablename__ = "materials_property_table_to_columns_connectivity"
    __table_args__ = (
        UniqueConstraint(
            "table_id",
            "sort_order",
            name="uq_mat_prop_tbl_cols_table_sort",
        ),
    )

    column_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials_property_tables.table_id", ondelete="CASCADE"),
        nullable=False,
    )
    column_property_type: Mapped[str] = mapped_column(String(63), nullable=False)
    column_units: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    property_table: Mapped["MaterialPropertyTable"] = relationship(
        "MaterialPropertyTable",
        back_populates="columns",
    )
    values: Mapped[list["MaterialPropertyColumnValue"]] = relationship(
        "MaterialPropertyColumnValue",
        back_populates="column",
        cascade="all, delete-orphan",
    )


class MaterialPropertyColumnValue(Base):
    __tablename__ = "materials_property_column_values"

    column_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials_property_table_to_columns_connectivity.column_id", ondelete="CASCADE"),
        primary_key=True,
    )
    point_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)

    column: Mapped["MaterialPropertyTableColumn"] = relationship(
        "MaterialPropertyTableColumn",
        back_populates="values",
    )
