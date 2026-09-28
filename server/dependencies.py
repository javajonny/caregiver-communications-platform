"""
FastAPI Dependency Injection Helpers

Provides reusable dependencies for common patterns like audit logging.
"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from database import get_db
from authentication import get_current_active_user
from services.audit import AuditService
from models import Staff


def get_audit_service(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
) -> AuditService:
    """
    FastAPI dependency that provides an initialized AuditService
    with the current user's context (ID, IP, User-Agent).
    
    Usage in endpoint:
        @router.get("/clients/{id}")
        def get_client(id: int, audit: AuditService = Depends(get_audit_service)):
            audit.log_data_access("read", "clients", id)
            ...
    """
    return AuditService(
        db=db,
        user_id=current_user.id if current_user else None,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=getattr(request.state, 'user_agent', None)
    )


def get_audit_service_optional_user(
    request: Request,
    db: Session = Depends(get_db)
) -> AuditService:
    """
    AuditService dependency for endpoints where user may not be authenticated
    (e.g., login endpoint where we log failed attempts).
    """
    return AuditService(
        db=db,
        user_id=None,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=getattr(request.state, 'user_agent', None)
    )
