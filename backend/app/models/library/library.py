from sqlalchemy import Float, ForeignKey, SmallInteger, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional, TYPE_CHECKING

from app.database import Base

if TYPE_CHECKING:
    from app.models.library.press import PressMode


class TimeBetweenOperations(Base):
    __tablename__ = "time_between_operations"

    first_operation_template_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    second_operation_template_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    press_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("press_modes.id", ondelete="CASCADE"), primary_key=True)

    time_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_sigma: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    press: Mapped["PressMode"] = relationship("PressMode")
