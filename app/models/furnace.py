from sqlalchemy import String, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class FurnaceClass(Base):
    __tablename__ = "furnace_class"

    furnace_class_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    furnace_class_name: Mapped[str | None] = mapped_column(String(1023), nullable=True)

