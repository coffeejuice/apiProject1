from sqlalchemy import Integer, ForeignKey, Boolean, text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional
from app.database import Base


class PressDieMap(Base):
    __tablename__ = "press_die_map"

    press_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("presses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    die_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("dies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_matching_as_top: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_matching_as_bottom: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_matching_as_left: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    is_matching_as_right: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
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
    obsolete_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    press = relationship("Press")
    die = relationship("Die")
