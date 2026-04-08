from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


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
