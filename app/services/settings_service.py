import time
from typing import Any, Dict, Optional, Type, TypeVar
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from app.models.settings import Setting, SettingScope

T = TypeVar("T")

class SettingsService:
    def __init__(self, ttl_seconds: int = 60):
        self._cache: Dict[str, Dict[str, Any]] = {}  # {cache_key: {"value": val, "expires_at": ts}}
        self._ttl = ttl_seconds

    def _get_cache_key(self, domain: str, key: str, scope_ids: Dict[str, Optional[int]]) -> str:
        tenant_id = scope_ids.get("tenant_id")
        user_id = scope_ids.get("user_id")
        return f"{domain}:{key}:{tenant_id}:{user_id}"

    def get(self, db: Session, key: str, domain: str = "default", user_id: Optional[int] = None, tenant_id: Optional[int] = None, default: Any = None) -> Any:
        scope_ids = {"user_id": user_id, "tenant_id": tenant_id}
        cache_key = self._get_cache_key(domain, key, scope_ids)
        
        # Check cache
        cached = self._cache.get(cache_key)
        if cached and cached["expires_at"] > time.time():
            return cached["value"]

        # Resolution priority: User -> Tenant -> Global -> Default
        stmt = select(Setting).where(
            and_(
                Setting.domain == domain,
                Setting.key == key,
                or_(
                    Setting.scope == SettingScope.GLOBAL,
                    and_(Setting.scope == SettingScope.TENANT, Setting.tenant_id == tenant_id),
                    and_(Setting.scope == SettingScope.USER, Setting.user_id == user_id)
                )
            )
        )
        results = db.execute(stmt).scalars().all()
        
        # Priority mapping
        value = default
        if results:
            priority_map = {SettingScope.USER: 2, SettingScope.TENANT: 1, SettingScope.GLOBAL: 0}
            sorted_settings = sorted(results, key=lambda s: priority_map.get(s.scope, -1), reverse=True)
            value = sorted_settings[0].value

        # Update cache
        self._cache[cache_key] = {
            "value": value,
            "expires_at": time.time() + self._ttl
        }
        return value

    def get_bool(self, db: Session, key: str, domain: str = "default", **kwargs) -> bool:
        val = self.get(db, key, domain=domain, **kwargs)
        try:
            return bool(val)
        except (ValueError, TypeError):
            return bool(kwargs.get("default", False))

    def get_int(self, db: Session, key: str, domain: str = "default", **kwargs) -> int:
        val = self.get(db, key, domain=domain, **kwargs)
        try:
            return int(val)
        except (ValueError, TypeError):
            return int(kwargs.get("default", 0))

    def get_float(self, db: Session, key: str, domain: str = "default", **kwargs) -> float:
        val = self.get(db, key, domain=domain, **kwargs)
        try:
            return float(val)
        except (ValueError, TypeError):
            return float(kwargs.get("default", 0.0))

    def get_string(self, db: Session, key: str, domain: str = "default", **kwargs) -> str:
        val = self.get(db, key, domain=domain, **kwargs)
        return str(val) if val is not None else str(kwargs.get("default", ""))

    def get_json(self, db: Session, key: str, domain: str = "default", **kwargs) -> Any:
        return self.get(db, key, domain=domain, **kwargs)

    def set_setting(self, db: Session, key: str, value: Any, domain: str = "default", scope: SettingScope = SettingScope.GLOBAL, 
                    tenant_id: Optional[int] = None, user_id: Optional[int] = None):
        # Find existing or create new
        stmt = select(Setting).where(
            and_(
                Setting.domain == domain,
                Setting.key == key,
                Setting.scope == scope,
                Setting.tenant_id == tenant_id,
                Setting.user_id == user_id
            )
        )
        setting = db.execute(stmt).scalar_one_or_none()
        
        if setting:
            setting.value = value
        else:
            setting = Setting(domain=domain, key=key, value=value, scope=scope, tenant_id=tenant_id, user_id=user_id)
            db.add(setting)
        
        db.commit()
        db.refresh(setting)
        
        # Invalidate related cache entries
        keys_to_delete = [ck for ck in self._cache if ck.startswith(f"{domain}:{key}:")]
        for ck in keys_to_delete:
            del self._cache[ck]
            
        return setting

    def delete_setting(self, db: Session, setting_id: int):
        setting = db.get(Setting, setting_id)
        if setting:
            domain = setting.domain
            key = setting.key
            db.delete(setting)
            db.commit()
            
            # Invalidate cache
            keys_to_delete = [ck for ck in self._cache if ck.startswith(f"{domain}:{key}:")]
            for ck in keys_to_delete:
                del self._cache[ck]
            return True
        return False

# Global instance
settings_service = SettingsService()
