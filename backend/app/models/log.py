from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, BigInteger, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional
import uuid
import enum
from app.database import Base
from app.models.server import ServerType


class LogLevel(enum.Enum):
    """'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'"""
    debug = "DEBUG"
    info = "INFO"
    warning = "WARNING"
    error = "ERROR"
    critical = "CRITICAL"


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    logger: Mapped[ServerType] = mapped_column(SQLEnum(ServerType, native_enum=False), nullable=False)
    level: Mapped[LogLevel] = mapped_column(SQLEnum(LogLevel, native_enum=False), nullable=False)
    msg: Mapped[str] = mapped_column(Text, nullable=False)
    logger_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sql_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    process_version_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(INET, nullable=True)


