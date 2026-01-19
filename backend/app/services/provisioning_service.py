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

        if not isinstance(data, dict):
            # The tree format must be a dict
            return {"applied": 0, "skipped": 0, "error": "Invalid format: Expected dict for tree structure"}

        applied_count = 0
        skipped_count = 0

        def process_node(node, prefix=""):
            nonlocal applied_count, skipped_count
            
            for key, value in node.items():
                current_key = f"{prefix}{key}"
                
                if isinstance(value, dict):
                    # Recurse
                    process_node(value, f"{current_key}.")
                else:
                    # Leaf node - this is a setting
                    if only_missing:
                        existing = settings_service.get(db, current_key)
                        if existing is not None:
                            skipped_count += 1
                            continue

                    settings_service.set_setting(
                        db, 
                        key=current_key, 
                        value=value, 
                        scope=SettingScope.GLOBAL
                    )
                    applied_count += 1

        process_node(data)

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
