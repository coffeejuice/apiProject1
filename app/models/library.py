from sqlalchemy import String, Text, JSON, DateTime, ForeignKey, Index, Enum as SQLEnum, Boolean, SmallInteger
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import Optional
import uuid
import enum
from app.database import Base



class OperationsLibrary(Base):
    __tablename__ = "operations_library"

    type_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    parent_type_id: Mapped[Optional[int]] = mapped_column(SmallInteger, ForeignKey("operations_library.type_id", ondelete="RESTRICT"), nullable=True)
    auto_create_children: Mapped[Optional[str]] = mapped_column(String(63), default=None, nullable=True)
    row: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    process_fixed_row: Mapped[Optional[int]] = mapped_column(SmallInteger, default=None, nullable=True)
    allow_copies: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text_id: Mapped[str] = mapped_column(String(511), nullable=False)
    library_name: Mapped[str] = mapped_column(String(255), nullable=False)
    process_name: Mapped[str] = mapped_column(String(255), nullable=False)
    labels: Mapped[Optional[str]] = mapped_column(String(1023), default=None, nullable=True)
    labels_regex: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    db_column_names: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    foreign_keys: Mapped[Optional[str]] = mapped_column(String(1023), default=None, nullable=True)
    is_simulation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_geometry: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_die_assembly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_custom_die_assembly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_press: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_feed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_top_die: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_bottom_die: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_speed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_billet_category: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_heating_category: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_forming_category: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_forming_operation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_surface_treatment_operation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deformation_type: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    speed_column_name: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    tooltip_image: Mapped[Optional[bytes]] = mapped_column(BYTEA, default=None, nullable=True)
    trigger: Mapped[Optional[str]] = mapped_column(String(63), default=None, nullable=True)
    is_initialize: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_accumulate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_keep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_obsolete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent: Mapped[Optional["OperationsLibrary"]] = relationship("OperationsLibrary", remote_side=[type_id])

