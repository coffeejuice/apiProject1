from sqlalchemy import ForeignKey, BigInteger, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.library import OperationsLibrary
    from app.models.document.process import ProcessVersion

class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("operations.id", ondelete="CASCADE"), nullable=True)
    type_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("operations_library.type_id", ondelete="RESTRICT"), nullable=False)
    row: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    process_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("process_versions.process_version_id", ondelete="CASCADE"), nullable=False)

    # Relationships
    parent: Mapped[Optional["Operation"]] = relationship("Operation", remote_side=[id])
    library: Mapped["OperationsLibrary"] = relationship("OperationsLibrary")
    process_version: Mapped["ProcessVersion"] = relationship("ProcessVersion")


