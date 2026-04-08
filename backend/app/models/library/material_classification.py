from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialClassificationAxis(Base):
    __tablename__ = "material_classification_axes"
    __table_args__ = (
        UniqueConstraint("key", name="uq_material_classification_axes_key"),
    )

    axis_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String(127),
        nullable=False,
    )
    name: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    selection_mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="multi",
        server_default=text("'multi'"),
    )
    hierarchy_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
        server_default=text("3"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    is_filter_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
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
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    values: Mapped[list["MaterialClassificationValue"]] = relationship(
        "MaterialClassificationValue",
        back_populates="axis",
        cascade="all, delete-orphan",
    )


class MaterialClassificationValue(Base):
    __tablename__ = "material_classification_values"
    __table_args__ = (
        UniqueConstraint("axis_id", "key", name="uq_material_classification_values_axis_key"),
    )

    value_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    axis_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("material_classification_axes.axis_id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(
        String(127),
        nullable=False,
    )
    name: Mapped[Any] = mapped_column(JSONB, nullable=False)
    color: Mapped[Optional[str]] = mapped_column(String(63), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
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
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    axis: Mapped["MaterialClassificationAxis"] = relationship(
        "MaterialClassificationAxis",
        back_populates="values",
    )
    assignments: Mapped[list["MaterialClassificationAssignment"]] = relationship(
        "MaterialClassificationAssignment",
        back_populates="classification_value",
        cascade="all, delete-orphan",
    )


class MaterialClassificationAssignment(Base):
    __tablename__ = "material_classification_assignments"

    material_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("materials.material_id", ondelete="CASCADE"),
        primary_key=True,
    )
    value_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("material_classification_values.value_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    material: Mapped["Material"] = relationship(
        "Material",
        back_populates="classification_assignments",
    )
    classification_value: Mapped["MaterialClassificationValue"] = relationship(
        "MaterialClassificationValue",
        back_populates="assignments",
    )
