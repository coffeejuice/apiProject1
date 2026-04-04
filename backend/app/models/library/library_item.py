from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LibraryType(enum.Enum):
    die = "die"
    die_assembly = "die_assembly"
    press = "press"
    press_mode = "press_mode"
    time_between_operations = "time_between_operations"
    material = "material"
    operation_type = "operation_type"


class Library(Base):
    __tablename__ = "library"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("library.id", ondelete="RESTRICT"),
        nullable=True,
        default=None,
        index=True,
    )
    type: Mapped[LibraryType] = mapped_column(
        SQLEnum(LibraryType, name="library_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    props: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    is_obsolete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent: Mapped[Optional["Library"]] = relationship("Library", remote_side=[id])
