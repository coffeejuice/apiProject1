from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import String, Integer, DateTime, ForeignKey, BigInteger, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.document.document import Document


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[Optional[int]] = mapped_column(
        SmallInteger,
        ForeignKey("material.material_id", ondelete="SET DEFAULT"),
        nullable=True,
        default=None,
    )
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

    owner: Mapped["User"] = relationship("User", back_populates="project_owner")
    documents: Mapped[List["Document"]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )
