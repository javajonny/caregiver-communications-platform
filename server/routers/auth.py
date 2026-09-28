from datetime import datetime, timedelta
from typing import Optional, Tuple
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import Staff
from authentication import (
    verify_password,
    create_session,
    get_current_user_and_session,
    logout_session,
    get_password_hash,
    IDLE_TIMEOUT_MINUTES,
    ABSOLUTE_SESSION_TTL_MINUTES,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    idle_timeout_minutes: int = IDLE_TIMEOUT_MINUTES
    absolute_expires_at: datetime
    must_change_password: bool = False


@router.post("/login", response_model=TokenOut)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    from services.audit import AuditService
    
    # Create audit service (user not authenticated yet)
    audit = AuditService(
        db=db,
        user_id=None,
        ip=getattr(request.state, 'client_ip', request.client.host if request.client else None),
        user_agent=request.headers.get("user-agent")
    )
    
    staff: Optional[Staff] = (
        db.query(Staff).filter(Staff.work_email == str(payload.email).lower()).first()
    )
    
    if not staff or not staff.is_active:
        audit.log_security_event(
            event_type="login_failure",
            severity="warning",
            description=f"Failed login attempt for email: {payload.email}",
            additional_data={"reason": "user_not_found_or_inactive"}
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, staff.password_hash or ""):
        audit.user_id = staff.id  # Now we know who attempted
        audit.log_security_event(
            event_type="login_failure",
            severity="warning",
            description=f"Failed login attempt for user {staff.id}: incorrect password",
            additional_data={"reason": "incorrect_password"}
        )
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_session(
        db=db,
        staff_id=staff.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Log successful login
    audit.user_id = staff.id
    audit.log_security_event(
        event_type="login_success",
        severity="info",
        description=f"User {staff.id} ({staff.work_email}) logged in successfully"
    )
    db.commit()

    absolute_expires_at = datetime.utcnow() + timedelta(minutes=ABSOLUTE_SESSION_TTL_MINUTES)

    return TokenOut(
        access_token=token,
        absolute_expires_at=absolute_expires_at,
        must_change_password=staff.must_change_password,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    reason: str = "user_initiated",
    db: Session = Depends(get_db),
    auth=Depends(get_current_user_and_session),
):
    from services.audit import AuditService
    
    staff, session = auth
    
    # Determine event type and description based on reason
    event_type = "logout"
    description = f"User {staff.id} logged out"
    
    if reason == "client_timeout":
        event_type = "session_timeout"
        description = f"User {staff.id} logged out due to client-side inactivity"
    elif reason == "session_expired":
        event_type = "session_expired"
        description = f"User {staff.id} logged out due to session expiration"
    
    # Log logout event
    audit = AuditService(
        db=db,
        user_id=staff.id,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=request.headers.get("user-agent")
    )
    audit.log_security_event(
        event_type=event_type,
        severity="info",
        description=description,
        additional_data={"reason": reason}
    )
    
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header.split(" ", 1)[1]
    logout_session(db, token)
    db.commit()
    return


from utils import validate_password_strength

@router.put("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    auth: Tuple[Staff, str] = Depends(get_current_user_and_session),
):
    from services.audit import AuditService
    
    staff, _ = auth

    if not verify_password(payload.old_password, staff.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")

    validate_password_strength(payload.new_password)

    staff.password_hash = get_password_hash(payload.new_password)
    staff.must_change_password = False
    
    # Log password change
    audit = AuditService(
        db=db,
        user_id=staff.id,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=request.headers.get("user-agent")
    )
    audit.log_security_event(
        event_type="password_change",
        severity="info",
        description=f"User {staff.id} changed their password"
    )
    
    db.commit()
    return


@router.get("/me")
def me(auth=Depends(get_current_user_and_session), request: Request = None, db: Session = Depends(get_db)):
    staff, session = auth
    
    # Get role name for RBAC
    from models import StaffRole
    role = db.query(StaffRole).filter(StaffRole.id == staff.role_id).first()
    role_name = role.role_name if role else None
    
    # Build full URL for profile image
    profile_image_url = None
    if staff.profile_image_path:
        # Get base URL from environment or construct from request
        base_url = os.getenv("BASE_URL")
        if not base_url and request:
            # Construct base URL from request (works in Docker)
            scheme = "https" if request.url.scheme == "https" else "http"
            base_url = f"{scheme}://{request.headers.get('host', 'localhost:8443')}"
        elif not base_url:
            base_url = "https://localhost:8443"
        
        profile_image_url = f"{base_url}/uploads/staff/{staff.profile_image_path}"
    
    return {
        "id": staff.id,
        "first_name": staff.first_name,
        "last_name": staff.last_name,
        "email": staff.work_email,
        "work_phone": staff.work_phone,
        "profile_image_url": profile_image_url,
        "role_id": staff.role_id,
        "role_name": role_name,
        "assigned_location_id": staff.assigned_location_id,
        "session_id": session.id,
        "last_activity": session.last_activity,
    }
