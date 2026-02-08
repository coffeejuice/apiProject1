from sqlalchemy import ForeignKey, BigInteger, Integer, SmallInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING
from app.database import Base

if TYPE_CHECKING:
    from app.models.library import OperationsLibrary
    from app.models.document.document import DocumentVersion

class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("operations.id", ondelete="CASCADE"), nullable=True)
    type_id: Mapped[int] = mapped_column(SmallInteger, ForeignKey("operations_library.type_id", ondelete="RESTRICT"), nullable=False)
    row: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("document_versions.document_version_id", ondelete="CASCADE"), nullable=False)
    parameters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    parent: Mapped[Optional["Operation"]] = relationship("Operation", remote_side=[id])
    library: Mapped["OperationsLibrary"] = relationship("OperationsLibrary")
    document_version: Mapped["DocumentVersion"] = relationship("DocumentVersion")


