import time
from typing import Any, Dict, Optional, Type, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from app.models.settings import Setting, SettingScope

T = TypeVar("T")

class SettingsService:
    def __init__(self, ttl: int = 60):
        self._cache: Dict[str, tuple[Any, float]] = {}  # {cache_key: (value, expires_at)}
        self._ttl = ttl

    def _get_cache_key(self, key: str, user_id: Optional[int] = None) -> str:
        return f"{key}:{user_id or 'none'}"

    def get(self, db: Session, key: str, user_id: Optional[int] = None, default: Any = None) -> Any:
        cache_key = self._get_cache_key(key, user_id)
        
        # Check cache
        cached = self._cache.get(cache_key)
        if cached and cached[1] > time.time():
            return cached[0]

        # Priority 1: User Override
        if user_id:
            stmt = select(Setting.value).where(
                Setting.key == key,
                Setting.scope == SettingScope.USER,
                Setting.user_id == user_id
            )
            val = db.execute(stmt).scalar()
            if val is not None:
                self._cache[cache_key] = (val, time.time() + self._ttl)
                return val

        # Priority 2: Global Default
        stmt = select(Setting.value).where(
            Setting.key == key,
            Setting.scope == SettingScope.GLOBAL
        )
        val = db.execute(stmt).scalar()
        
        if val is None:
            val = default
            
        self._cache[cache_key] = (val, time.time() + self._ttl)
        return val

    def get_bool(self, db: Session, key: str, user_id: Optional[int] = None, default: bool = False) -> bool:
        val = self.get(db, key, user_id, default)
        return bool(val)

    def get_int(self, db: Session, key: str, user_id: Optional[int] = None, default: int = 0) -> int:
        val = self.get(db, key, user_id, default)
        return int(val)

    def get_float(self, db: Session, key: str, user_id: Optional[int] = None, default: float = 0.0) -> float:
        val = self.get(db, key, user_id, default)
        return float(val)

    def get_string(self, db: Session, key: str, user_id: Optional[int] = None, default: str = "") -> str:
        val = self.get(db, key, user_id, default)
        return str(val)

    def get_json(self, db: Session, key: str, user_id: Optional[int] = None, default: Any = None) -> Any:
        return self.get(db, key, user_id, default)

    def set_setting(self, db: Session, key: str, value: Any, scope: SettingScope = SettingScope.GLOBAL, 
                    user_id: Optional[int] = None):
        # Enforce scope rules
        if scope == SettingScope.GLOBAL:
            user_id = None
        
        # Find existing or create new
        stmt = select(Setting).where(
            and_(
                Setting.key == key,
                Setting.scope == scope,
                Setting.user_id == user_id
            )
        )
        setting = db.execute(stmt).scalar_one_or_none()
        
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value, scope=scope, user_id=user_id)
            db.add(setting)
        
        db.commit()
        db.refresh(setting)
        
        # Invalidate related cache entries
        keys_to_delete = [ck for ck in self._cache if ck.startswith(f"{key}:")]
        for ck in keys_to_delete:
            del self._cache[ck]
            
        return setting

    def delete_setting(self, db: Session, setting_id: int):
        setting = db.get(Setting, setting_id)
        if setting:
            key = setting.key
            db.delete(setting)
            db.commit()
            
            # Invalidate cache
            keys_to_delete = [ck for ck in self._cache if ck.startswith(f"{key}:")]
            for ck in keys_to_delete:
                del self._cache[ck]
            return True
        return False

# Global instance
settings_service = SettingsService()
