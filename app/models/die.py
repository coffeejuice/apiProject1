from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional
import uuid
import enum
from app.database import Base


class DieType(enum.Enum):
    """'flat', 'v_die', 'rounding', 'knife', 'gfm_die'"""
    flat = "flat"
    v_die = "v_die"
    rounding = "rounding"
    knife = "knife"
    gfm_die = "gfm_die"

