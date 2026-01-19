from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SQLEnum, Boolean, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional
import enum
from app.database import Base


class DieType(enum.Enum):
    flat = "flat"
    v_die = "v_die"
    rounding = "rounding"
    knife = "knife"
    gfm_die = "gfm_die"


class DieAssembly(Base):
    __tablename__ = "die_assembly"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    die_assembly_name: Mapped[str] = mapped_column(String(127), nullable=False)
    name: Mapped[str] = mapped_column(String(1023), nullable=False)
    die_type: Mapped[DieType] = mapped_column(SQLEnum(DieType, name="die_type_enum"), nullable=False)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    dies: Mapped[List["Die"]] = relationship("Die", back_populates="die_assembly")


class Die(Base):
    __tablename__ = "die"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    die_assembly_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("die_assembly.id", ondelete="RESTRICT"), nullable=True, default=None)

    die_name: Mapped[str] = mapped_column(String(127), nullable=False)
    name: Mapped[str] = mapped_column(String(1023), nullable=False)
    die_type: Mapped[DieType] = mapped_column(SQLEnum(DieType, name="die_type_enum"), nullable=False)

    die_template_file_name: Mapped[str] = mapped_column(String(1023), default="", nullable=True)
    die_assembly_name: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    press_die_match_code: Mapped[Optional[str]] = mapped_column(String(127), nullable=True)
    inventory_number: Mapped[str] = mapped_column(String(127), default="", nullable=True)

    is_matching_as_top: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_matching_as_bottom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_matching_as_minus_y: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_matching_as_plus_y: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    dimensions: Mapped[str] = mapped_column(String(4095), default="", nullable=True)

    is_obsolete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, onupdate=func.now())
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    die_assembly: Mapped[Optional["DieAssembly"]] = relationship("DieAssembly", back_populates="dies")

