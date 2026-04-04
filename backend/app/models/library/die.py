from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Any, Optional
from app.database import Base


class DieType(Base):
    __tablename__ = "die_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Any] = mapped_column(JSONB, nullable=False)


class DieAssembly(Base):
    __tablename__ = "die_assemblies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Any] = mapped_column(JSONB, nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    top_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dies.id", ondelete="SET NULL"), nullable=True)
    bottom_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dies.id", ondelete="SET NULL"), nullable=True)
    left_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dies.id", ondelete="SET NULL"), nullable=True)
    right_die_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("dies.id", ondelete="SET NULL"), nullable=True)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), server_default=func.now())
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    top_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[top_die_id])
    bottom_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[bottom_die_id])
    left_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[left_die_id])
    right_die: Mapped[Optional["Die"]] = relationship("Die", foreign_keys=[right_die_id])


class Die(Base):
    __tablename__ = "dies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[Any] = mapped_column(JSONB, nullable=False)
    die_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("die_types.id", ondelete="RESTRICT"), nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    die_template_file_name: Mapped[str] = mapped_column(String(1023), default="", nullable=True)
    inventory_number: Mapped[str] = mapped_column(String(127), default="", nullable=True)

    properties: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    is_obsolete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), server_default=func.now())
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    die_type_item: Mapped["DieType"] = relationship("DieType")
