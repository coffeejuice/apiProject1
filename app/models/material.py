from sqlalchemy import String, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.database import Base


class Material(Base):
    __tablename__ = "material"

    material_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_name: Mapped[str] = mapped_column(String(2047), nullable=False)
    material_path: Mapped[str] = mapped_column(String(2047), nullable=False)
    short_name: Mapped[str] = mapped_column(String(63), nullable=False, default="")
    density: Mapped[float] = mapped_column(Float, nullable=True, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)





