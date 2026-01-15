from sqlalchemy import String, Integer, Enum as SQLEnum, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
import enum
from app.database import Base

class SettingScope(enum.Enum):
    GLOBAL = "global"
    TENANT = "tenant"
    USER = "user"

class Setting(Base):
    __tablename__ = "settings"

    setting_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String, nullable=False, default="default", index=True)
    key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB, nullable=False)
    scope: Mapped[SettingScope] = mapped_column(
        SQLEnum(SettingScope, native_enum=False), 
        nullable=False, 
        default=SettingScope.GLOBAL
    )
    tenant_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint('domain', 'key', 'scope', 'tenant_id', 'user_id', name='uq_setting_domain_key_scope_tenant_user'),
    )
