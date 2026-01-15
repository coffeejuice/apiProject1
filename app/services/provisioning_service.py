import yaml
import os
from pathlib import Path
from sqlalchemy.orm import Session
from app.services.settings_service import settings_service
from app.models.settings import SettingScope

class ProvisioningService:
    def __init__(self, seed_dir: str = "seed"):
        self.seed_path = Path(seed_dir)

    def _parse_scope(self, scope_str: str) -> SettingScope:
        try:
            return SettingScope(scope_str.lower())
        except ValueError:
            return SettingScope.GLOBAL

    def apply_seed(self, db: Session, filename: str, only_missing: bool = False):
        filepath = self.seed_path / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Seed file {filename} not found")

        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        settings_list = data.get("settings", [])
        applied_count = 0
        skipped_count = 0

        for s in settings_list:
            domain = s.get("domain", "default")
            key = s.get("key")
            value = s.get("value")
            scope = self._parse_scope(s.get("scope", "global"))
            tenant_id = s.get("tenant_id")
            user_id = s.get("user_id")

            if only_missing:
                # Check if it exists
                existing = settings_service.get(db, key, domain=domain, user_id=user_id, tenant_id=tenant_id)
                if existing is not None:
                    skipped_count += 1
                    continue

            settings_service.set_setting(
                db, 
                key=key, 
                value=value, 
                domain=domain, 
                scope=scope, 
                tenant_id=tenant_id, 
                user_id=user_id
            )
            applied_count += 1

        return {"applied": applied_count, "skipped": skipped_count}

    def apply_all_seeds(self, db: Session, only_missing: bool = False):
        if not self.seed_path.exists():
            return {"message": "Seed directory not found"}

        # Sort files by name to ensure consistent order (e.g. v0001, v0002...)
        files = sorted([f.name for f in self.seed_path.glob("*.yaml")])
        results = {}
        for f in files:
            results[f] = self.apply_seed(db, f, only_missing=only_missing)
        
        return results

provisioning_service = ProvisioningService()
