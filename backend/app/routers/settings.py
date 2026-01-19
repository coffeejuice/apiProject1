from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.auth import get_current_user
from app.models.user import User
from app.schemas import SettingCreate, SettingUpdate, SettingResponse
from app.services.settings_service import settings_service
from app.models.settings import Setting, SettingScope
from sqlalchemy import select

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("/", response_model=List[SettingResponse])
def list_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: Optional[SettingScope] = None,
    key_like: Optional[str] = None
):
    # Simple check: only users with supervisor_id == 1 can list all settings
    # Otherwise, they might only see their own or global ones
    stmt = select(Setting)
    if current_user.supervisor_id != 1:
        # Restricted view for non-admins
        stmt = stmt.where(
            (Setting.scope == SettingScope.GLOBAL) |
            ((Setting.scope == SettingScope.USER) & (Setting.user_id == current_user.user_id))
        )
    
    if scope:
        stmt = stmt.where(Setting.scope == scope)
    if key_like:
        stmt = stmt.where(Setting.key.like(key_like))
        
    return db.execute(stmt).scalars().all()

@router.post("/", response_model=SettingResponse)
def create_or_update_setting(
    setting_in: SettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Authorization: only admins can set GLOBAL scope
    if setting_in.scope == SettingScope.GLOBAL and current_user.supervisor_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can set global settings"
        )
    
    # If USER scope, enforce current_user.user_id unless admin
    if setting_in.scope == SettingScope.USER:
        if current_user.supervisor_id != 1:
            setting_in.user_id = current_user.user_id
        elif setting_in.user_id is None:
            setting_in.user_id = current_user.user_id

    return settings_service.set_setting(
        db, 
        key=setting_in.key, 
        value=setting_in.value, 
        scope=setting_in.scope,
        user_id=setting_in.user_id
    )

@router.delete("/{setting_id}")
def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    setting = db.get(Setting, setting_id)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
        
    if current_user.supervisor_id != 1:
        if setting.scope != SettingScope.USER or setting.user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this setting"
            )
            
    settings_service.delete_setting(db, setting_id)
    return {"message": "Setting deleted"}

@router.get("/resolve/{key}")
def resolve_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # This endpoint demonstrates the resolution logic
    value = settings_service.get(
        db, 
        key=key, 
        user_id=current_user.user_id
    )
    return {"key": key, "resolved_value": value}

@router.post("/provision/apply")
def apply_all_provisions(
    only_missing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.supervisor_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can trigger provisioning"
        )
    
    from app.services.provisioning_service import provisioning_service
    return provisioning_service.apply_all_seeds(db, only_missing=only_missing)

@router.post("/provision/file/{filename}")
def apply_specific_provision(
    filename: str,
    only_missing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.supervisor_id != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can trigger provisioning"
        )
    
    from app.services.provisioning_service import provisioning_service
    try:
        return provisioning_service.apply_seed(db, filename, only_missing=only_missing)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
