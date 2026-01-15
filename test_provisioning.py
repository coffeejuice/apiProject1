import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.settings import Setting, SettingScope
from app.services.provisioning_service import provisioning_service
from sqlalchemy import select, delete

def test_provisioning():
    db = SessionLocal()
    try:
        # 1. Clear existing settings
        db.execute(delete(Setting))
        db.commit()
        print("Settings cleared.")

        # 2. Apply all seeds
        print("Applying all seeds...")
        results = provisioning_service.apply_all_seeds(db)
        print(f"Provisioning results: {results}")
        
        # Verify specific setting from v0003_settings.yaml
        stmt = select(Setting).where(Setting.domain == "svc", Setting.key == "worker.pool_size")
        setting = db.execute(stmt).scalar_one_or_none()
        assert setting is not None
        assert setting.value == 5
        print("✓ Verified setting from seed.")

        # 3. Test 'only_missing'
        # Modify the value in DB
        setting.value = 99
        db.commit()
        
        print("Re-applying seeds with only_missing=True...")
        results = provisioning_service.apply_all_seeds(db, only_missing=True)
        print(f"Re-provisioning results: {results}")
        
        # Should NOT have updated
        db.refresh(setting)
        assert setting.value == 99
        print("✓ Verified only_missing=True logic.")

        # 4. Test Overwrite (only_missing=False)
        print("Re-applying seeds with only_missing=False...")
        results = provisioning_service.apply_all_seeds(db, only_missing=False)
        
        db.refresh(setting)
        assert setting.value == 5
        print("✓ Verified overwrite logic.")

        print("Provisioning tests passed successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    try:
        test_provisioning()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
