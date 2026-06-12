import hmac
import ipaddress
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_password_hash
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.library_seed_service import LibrarySeedError, library_seed_service

router = APIRouter(prefix="/setup", tags=["setup"])
optional_bearer = HTTPBearer(auto_error=False)


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=255)
    setup_token: Optional[str] = Field(default=None, min_length=16, max_length=255)


def _get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        return None

    return db.execute(select(User).filter(User.user_id == user_id)).scalars().first()


def _is_loopback_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _authorize_admin_password_reset(
    request: Request,
    current_user: Optional[User],
    setup_token: Optional[str],
) -> None:
    if current_user is not None and current_user.supervisor_id == 1:
        return

    configured_token = settings.SETUP_ADMIN_RESET_TOKEN.strip()
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator authentication is required; setup token reset is not configured",
        )

    if not _is_loopback_request(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup token admin reset is only allowed from localhost",
        )

    if not setup_token or not hmac.compare_digest(setup_token, configured_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid setup reset token",
        )


@router.get("/status")
def setup_status(
    request: Request,
    db: Session = Depends(get_db),
):
    setup_data = library_seed_service.get_status(db)
    admin_user_exists = db.execute(
        select(User.user_id).filter(User.login == "admin")
    ).first() is not None
    if not admin_user_exists:
        admin_user_exists = db.execute(
            select(User.user_id).filter(User.user_id == 1)
        ).first() is not None

    setup_data["admin_user_exists"] = admin_user_exists
    setup_data["can_reset_admin_password_with_setup_token"] = bool(
        settings.SETUP_ADMIN_RESET_TOKEN.strip() and _is_loopback_request(request)
    )
    return setup_data


@router.post("/seed-library")
def seed_library(
    only_missing: bool = False,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    setup_data = library_seed_service.get_status(db)
    users_count = int(setup_data.get("counts", {}).get("users", 0))

    # First install bootstrap: allow seeding without auth only when users table is empty.
    if users_count > 0 and (current_user is None or current_user.supervisor_id != 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator authentication is required to run library seeding",
        )

    try:
        return library_seed_service.seed_library(
            db,
            only_missing=only_missing,
            triggered_by_user_id=current_user.user_id if current_user else None,
        )
    except LibrarySeedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/reset-admin-password")
def reset_admin_password(
    request: Request,
    payload: AdminPasswordResetRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(_get_optional_user),
):
    _authorize_admin_password_reset(request, current_user, payload.setup_token)

    admin_user = db.execute(select(User).filter(User.login == "admin")).scalars().first()
    if admin_user is None:
        admin_user = db.execute(select(User).filter(User.user_id == 1)).scalars().first()
    if admin_user is None:
        raise HTTPException(status_code=404, detail="Admin user not found")

    admin_user.password_hashed = get_password_hash(payload.new_password)
    db.add(admin_user)
    db.commit()

    return {
        "ok": True,
        "user_id": admin_user.user_id,
        "login": admin_user.login,
        "message": "Admin password updated",
    }
