from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from typing import List, Optional
import uuid
import enum
from app.database import Base


class SimulationStatus(enum.Enum):
    """'stop', 'queue', 'run', 'finished', 'error'"""
    stop = "stop"
    queue = "queue"
    run = "run"
    finished = "finished"
    error = "error"


class Priority(enum.Enum):
    """'Whenever', 'Normal', 'ASAP', 'Now'"""
    whenever = "Whenever"
    normal = "Normal"
    asap = "ASAP"
    now = "Now"

