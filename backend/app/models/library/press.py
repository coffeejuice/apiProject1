from sqlalchemy import Integer, SmallInteger, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Any, Optional
from app.database import Base


class Press(Base):
    __tablename__ = "presses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[Any] = mapped_column(JSONB, nullable=False)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    modes: Mapped[list["PressMode"]] = relationship("PressMode", back_populates="press")


class PressMode(Base):
    __tablename__ = "press_modes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    press_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("presses.id", ondelete="RESTRICT"), nullable=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_default_press_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), server_default=func.now())
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    press: Mapped[Optional["Press"]] = relationship("Press", back_populates="modes")
