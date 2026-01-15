import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.settings import Setting, SettingScope
from app.services.settings_service import settings_service
from app.models.user import User
from sqlalchemy import select, delete

def setup_test_data(db: Session):
    # Clear existing settings
    db.execute(delete(Setting))
    db.commit()

    user2 = db.execute(select(User).where(User.user_id == 2)).scalar_one_or_none()
    if not user2:
        user_id = 2
        dept_id = 1
    else:
        user_id = user2.user_id
        dept_id = user2.department_id

    # domain = 'svc'
    # key = 'worker.pool_size'
    
    # 1. Set Global Default
    settings_service.set_setting(db, "worker.pool_size", 3, domain="svc", scope=SettingScope.GLOBAL)
    
    # 2. Set Tenant Override
    settings_service.set_setting(db, "worker.pool_size", 5, domain="svc", scope=SettingScope.TENANT, tenant_id=dept_id)
    
    # 3. Set User Override
    settings_service.set_setting(db, "worker.pool_size", 10, domain="svc", scope=SettingScope.USER, user_id=user_id)

    # 4. Set another domain same key
    settings_service.set_setting(db, "worker.pool_size", 100, domain="other", scope=SettingScope.GLOBAL)

    return user_id, dept_id

def test_resolution():
    db = SessionLocal()
    try:
        user_id, dept_id = setup_test_data(db)
        
        # Test 1: User level resolution in 'svc'
        val = settings_service.get_int(db, "worker.pool_size", domain="svc", user_id=user_id, tenant_id=dept_id)
        print(f"Resolved 'svc' value for User {user_id} (Expected 10): {val}")
        assert val == 10
        
        # Test 2: Other domain resolution
        val = settings_service.get_int(db, "worker.pool_size", domain="other")
        print(f"Resolved 'other' value (Expected 100): {val}")
        assert val == 100
        
        # Test 3: Default domain resolution (should be None or fallback)
        val = settings_service.get(db, "worker.pool_size", domain="default", default=42)
        print(f"Resolved 'default' value (Expected 42): {val}")
        assert val == 42
        
        print("Resolution tests passed!")
        
    finally:
        db.close()

def test_caching():
    db = SessionLocal()
    try:
        user_id, dept_id = setup_test_data(db)
        
        # Prime cache for svc:worker.pool_size
        val1 = settings_service.get_int(db, "worker.pool_size", domain="svc", user_id=user_id, tenant_id=dept_id)
        
        # Change value in DB directly
        db.query(Setting).filter(
            Setting.domain == "svc", 
            Setting.key == "worker.pool_size", 
            Setting.scope == SettingScope.USER
        ).update({"value": 20})
        db.commit()
        
        # Should still be cached
        val2 = settings_service.get_int(db, "worker.pool_size", domain="svc", user_id=user_id, tenant_id=dept_id)
        print(f"Cached value (Expected 10): {val2}")
        assert val2 == 10
        
        # Update via service
        settings_service.set_setting(db, "worker.pool_size", 30, domain="svc", scope=SettingScope.USER, user_id=user_id)
        val3 = settings_service.get_int(db, "worker.pool_size", domain="svc", user_id=user_id, tenant_id=dept_id)
        print(f"Updated value after invalidation (Expected 30): {val3}")
        assert val3 == 30
        
        print("Caching tests passed!")
        
    finally:
        db.close()

if __name__ == "__main__":
    try:
        test_resolution()
        test_caching()
        print("All tests passed successfully!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
