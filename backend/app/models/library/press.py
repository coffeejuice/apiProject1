from sqlalchemy import String, Integer, SmallInteger, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class Press(Base):
    __tablename__ = "press"

    press_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    press_die_match_code: Mapped[str] = mapped_column(String(127), nullable=False)
    name: Mapped[str] = mapped_column(String(1023), nullable=False)

    modes: Mapped[list["PressMode"]] = relationship("PressMode", back_populates="press")


class PressMode(Base):
    __tablename__ = "press_mode"

    press_mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    press_mode_name: Mapped[str] = mapped_column(String(127), nullable=False)
    press_die_match_code: Mapped[str] = mapped_column(String(127), nullable=False)
    press_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("press.press_id", ondelete="RESTRICT"), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(1023), nullable=True)
    is_default_press_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)
    manipulators_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    automatic_feed_mode_is_on_when_bites_count: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    max_force: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    back_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    idle_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    working_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_dwell_speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_dwell_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_idle_stroke: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_idle_stroke: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    approaching_distance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    open_height_without_dies: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    power_limit: Mapped[Optional[list[dict]]] = mapped_column(JSONB, nullable=True, default=list)

    press: Mapped[Optional["Press"]] = relationship("Press", back_populates="modes")


