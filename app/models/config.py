from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SQLEnum
import enum
from app.database import Base


class ServerType(enum.Enum):
    pre = "pre"
    post = "post"
    simulation = "simulation"
    sql = "sql"
    client = "client"
    file_server = "file_server"


class UiLanguage(enum.Enum):
    en = "en"
    ru = "ru"
    zh_hans = "zh_hans"


class Config(Base):
    __tablename__ = "config"

    server_type: Mapped[ServerType] = mapped_column(
        SQLEnum(ServerType, native_enum=False),
        primary_key=True
    )
    config_json: Mapped[dict | None] = mapped_column(JSONB, default=None, nullable=True)


