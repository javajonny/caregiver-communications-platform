from datetime import datetime, timedelta
import os
import hashlib
import secrets
from typing import Optional, Tuple

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import Staff, UserSession


# ================================
# Configuration
# ================================

# HIPAA-oriented defaults (adjust via env if needed)
IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "10"))  # auto-logoff after inactivity
ABSOLUTE_SESSION_TTL_MINUTES = int(os.getenv("SESSION_ABSOLUTE_TTL_MINUTES", "720"))  # 12 hours max lifetime


# ================================
# Token utilities
# ================================

def _hash_token(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
	# URL-safe 32-byte secret
	return secrets.token_urlsafe(32)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# ================================
# Session management
# ================================

def create_session(
	db: Session,
	staff_id: int,
	ip_address: Optional[str] = None,
	user_agent: Optional[str] = None,
) -> str:
	"""Create a new session, store hashed token server-side, and return raw token to client."""
	token = generate_session_token()
	token_hash = _hash_token(token)

	now = datetime.utcnow()
	absolute_expiry = now + timedelta(minutes=ABSOLUTE_SESSION_TTL_MINUTES)

	session = UserSession(
		staff_id=staff_id,
		session_token_hash=token_hash,
		ip_address=ip_address,
		user_agent=user_agent,
		created_at=now,
		expires_at=absolute_expiry,
		last_activity=now,
		is_active=True,
	)
	db.add(session)
	db.commit()
	return token


def _get_valid_session(
	db: Session,
	token: str,
	ip_address: Optional[str] = None,
	user_agent: Optional[str] = None,
) -> Tuple[UserSession, Staff]:
	if not token:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session token")

	token_hash = _hash_token(token)
	session = (
		db.query(UserSession)
		.filter(
			UserSession.session_token_hash == token_hash,
			UserSession.is_active == True,
		)
		.first()
	)
	if not session:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

	# Import AuditService here to avoid circular imports at module level
	from services.audit import AuditService

	# Absolute expiration
	now = datetime.utcnow()
	if session.expires_at and session.expires_at < now:
		session.is_active = False
		
		# Log security event for expiration
		audit = AuditService(db=db, user_id=session.staff_id, ip=ip_address, user_agent=user_agent)
		audit.log_security_event(
			event_type="session_expired",
			severity="info",
			description=f"Session expired for user {session.staff_id} (Absolute TTL)",
			additional_data={"reason": "absolute_ttl_exceeded"}
		)
		
		db.commit()
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

	# Idle timeout
	idle_cutoff = now - timedelta(minutes=IDLE_TIMEOUT_MINUTES)
	if session.last_activity and session.last_activity < idle_cutoff:
		session.is_active = False
		
		# Log security event for idle timeout
		audit = AuditService(db=db, user_id=session.staff_id, ip=ip_address, user_agent=user_agent)
		audit.log_security_event(
			event_type="session_timeout",
			severity="info",
			description=f"Session timed out for user {session.staff_id} due to inactivity",
			additional_data={"reason": "idle_timeout", "idle_minutes": IDLE_TIMEOUT_MINUTES}
		)
		
		db.commit()
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session timed out due to inactivity")

	# Load user
	staff = db.query(Staff).filter(Staff.id == session.staff_id, Staff.is_active == True).first()
	if not staff:
		session.is_active = False
		db.commit()
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

	# Sliding activity window: update last_activity on each valid request
	session.last_activity = now
	db.commit()
	return session, staff


_bearer = HTTPBearer(auto_error=False)


async def get_current_user_and_session(
	request: Request,
	db: Session = Depends(get_db),
	creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Tuple[Staff, UserSession]:
	"""FastAPI dependency to enforce active session with idle timeout and absolute TTL."""
	if creds is None or creds.scheme.lower() != "bearer":
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

	token = creds.credentials
	
	# Extract context for logging
	ip = getattr(request.state, 'client_ip', request.client.host if request.client else None)
	ua = request.state.user_agent if hasattr(request.state, 'user_agent') else request.headers.get("user-agent")
	
	session, staff = _get_valid_session(db, token, ip_address=ip, user_agent=ua)

	# annotate request for audit middleware if desired
	request.state.user_id = staff.id
	request.state.session_id = session.id
	return staff, session


async def get_current_active_user(
	request: Request,
	db: Session = Depends(get_db),
	creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Staff:
	staff, _ = await get_current_user_and_session(request, db, creds)
	return staff


def logout_session(
	db: Session,
	token: str,
):
	token_hash = _hash_token(token)
	session = (
		db.query(UserSession)
		.filter(UserSession.session_token_hash == token_hash, UserSession.is_active == True)
		.first()
	)
	if session:
		session.is_active = False
		db.commit()

