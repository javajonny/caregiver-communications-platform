"""
Authorization helpers for role-based and resource-based access control.

This module provides dependency functions for implementing fine-grained
authorization in FastAPI endpoints beyond basic authentication.

CURRENT STATE: All endpoints require authentication (login required).
FUTURE: Use these helpers to add role-based restrictions.

Example usage patterns:

1. Require specific role:
   @router.get("/admin-only")
   def admin_endpoint(user: Staff = Depends(require_role("admin"))):
       ...

2. Require one of multiple roles:
   @router.get("/staff-management")
   def manage_staff(user: Staff = Depends(require_roles(["admin", "manager"]))):
       ...

3. Custom resource-based check:
   @router.get("/clients/{client_id}")
   def get_client(
       client_id: int,
       user: Staff = Depends(get_current_active_user),
       db: Session = Depends(get_db)
   ):
       # Check if user has access to this client via shift assignment
       if not has_client_access(db, user, client_id):
           raise HTTPException(403, "No access to this client")
       ...
"""

from functools import wraps
from typing import List, Callable
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from authentication import get_current_active_user
from database import get_db
from models import Staff, StaffRole, Shift, ShiftAssignment, ShiftPositionClient, ClientProgramEnrollment


# Role IDs (admin, director, site_director, dsp)
ROLE_ADMIN = 1
ROLE_DIRECTOR = 2
ROLE_SITE_DIRECTOR = 3
ROLE_DSP = 4


# ================================
# Role-based authorization
# ================================

def require_role(role_name: str) -> Callable:
    """
    Dependency that requires the authenticated user to have a specific role.
    
    Usage:
        @router.delete("/dangerous-operation")
        def delete_all(user: Staff = Depends(require_role("admin"))):
            ...
    
    Args:
        role_name: The required role name (e.g., "admin", "manager", "caregiver")
    
    Returns:
        A FastAPI dependency that validates role and returns the user
    
    Raises:
        HTTPException 403 if user doesn't have the required role
    """
    async def check_role(
        user: Staff = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> Staff:
        role = db.query(StaffRole).filter(StaffRole.id == user.role_id).first()
        if not role or role.role_name != role_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role_name} role"
            )
        return user
    return check_role


def require_roles(role_names: List[str]) -> Callable:
    """
    Dependency that requires the authenticated user to have one of the specified roles.
    
    Usage:
        @router.post("/schedules")
        def create_schedule(user: Staff = Depends(require_roles(["admin", "manager"]))):
            ...
    
    Args:
        role_names: List of acceptable role names
    
    Returns:
        A FastAPI dependency that validates role and returns the user
    
    Raises:
        HTTPException 403 if user doesn't have any of the required roles
    """
    async def check_roles(
        user: Staff = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ) -> Staff:
        role = db.query(StaffRole).filter(StaffRole.id == user.role_id).first()
        if not role or role.role_name not in role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {', '.join(role_names)}"
            )
        return user
    return check_roles


# ================================
# Resource-based authorization
# ================================

def has_client_access(db: Session, user: Staff, client_id: int) -> bool:
    """
    Check if a staff member has access to a specific client.
    
    Access rules:
    - Admins: full access to all clients
    - Managers: access to clients in their program locations (if you implement staff_location_assignments)
    - Caregivers: access to clients assigned via active shifts
    
    Args:
        db: Database session
        user: The staff member to check
        client_id: The client ID to check access for
    
    Returns:
        True if user has access, False otherwise
    """
    # Get user's role
    role = db.query(StaffRole).filter(StaffRole.id == user.role_id).first()
    if not role:
        return False
    
    # Admin has access to everything
    if role.role_name == "admin":
        return True
    
    # Manager access: check program location assignments (if implemented)
    # For now, managers get full access like admins
    if role.role_name == "manager":
        return True
    
    # Caregiver: check shift-based access
    # User must be assigned to a shift that includes this client
    has_shift_access = (
        db.query(ShiftAssignment)
        .join(ShiftPositionClient, ShiftAssignment.shift_position_id == ShiftPositionClient.shift_position_id)
        .filter(
            ShiftAssignment.staff_id == user.id,
            ShiftPositionClient.client_id == client_id
        )
        .first()
    ) is not None
    
    return has_shift_access


def has_shift_access(db: Session, user: Staff, shift_id: int) -> bool:
    """
    Check if a staff member has access to a specific shift.
    
    Access rules:
    - Admins/Managers: full access
    - Caregivers: access only to shifts they're assigned to
    
    Args:
        db: Database session
        user: The staff member to check
        shift_id: The shift ID to check access for
    
    Returns:
        True if user has access, False otherwise
    """
    role = db.query(StaffRole).filter(StaffRole.id == user.role_id).first()
    if not role:
        return False
    
    # Admin/Manager: full access
    if role.role_name in ["admin", "manager"]:
        return True
    
    # Caregiver: must be assigned to the shift
    is_assigned = (
        db.query(ShiftAssignment)
        .filter(
            ShiftAssignment.staff_id == user.id,
            ShiftAssignment.shift_id == shift_id
        )
        .first()
    ) is not None
    
    return is_assigned

