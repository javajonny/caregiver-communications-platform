from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import bcrypt

from authentication import get_current_active_user
from authorization import require_roles, ROLE_ADMIN, ROLE_DIRECTOR, ROLE_SITE_DIRECTOR, ROLE_DSP
from database import get_db
from models import Staff, StaffRole, Shift, ShiftAssignment
from schemas import (
    StaffCreate, StaffUpdate, StaffOut,
    StaffRoleCreate, StaffRoleUpdate, StaffRoleOut
)
from utils import get_or_404, validate_password_strength

router = APIRouter(
    prefix="/staff",
    tags=["Staff"],
    dependencies=[Depends(get_current_active_user)]
)


@router.get("", response_model=list[StaffOut])
def get_all_staff(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get staff members scoped by role:
    - Admin: All staff
    - Director: Directors, Site Directors, DSPs (not Admins)
    - Site Director: Site Directors and DSPs
    - DSP: Staff at locations where they have shift assignments
    """
    query = db.query(Staff, StaffRole.role_name).join(StaffRole, Staff.role_id == StaffRole.id)
    
    # Role hierarchy filtering
    if current_user.role_id == ROLE_DIRECTOR:
        # Directors see: Director, Site Director, DSP (not Admin)
        query = query.filter(Staff.role_id >= ROLE_DIRECTOR)  # role_id >= 2
    elif current_user.role_id == ROLE_SITE_DIRECTOR:
        # Site Directors see: all Site Directors and DSPs (for shift coverage)
        query = query.filter(Staff.role_id >= ROLE_SITE_DIRECTOR)  # role_id >= 3
    elif current_user.role_id == ROLE_DSP:
        # DSPs see: Staff who work at the same locations (via shifts) + Site Directors managing those locations
        # Get location IDs where current DSP has shifts
        dsp_location_ids = db.query(Shift.program_location_id).join(
            ShiftAssignment, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            Shift.cancelled_at.is_(None)
        ).distinct().all()
        location_ids = [loc_id for (loc_id,) in dsp_location_ids]
        
        if location_ids:
            # Find other staff who also have shifts at these locations
            coworker_ids = db.query(ShiftAssignment.staff_id).join(
                Shift, ShiftAssignment.shift_id == Shift.id
            ).filter(
                Shift.program_location_id.in_(location_ids),
                Shift.cancelled_at.is_(None)
            ).distinct().all()
            coworker_staff_ids = [staff_id for (staff_id,) in coworker_ids]
            
            # Also include Site Directors assigned to these locations
            site_director_ids = db.query(Staff.id).filter(
                Staff.role_id == ROLE_SITE_DIRECTOR,
                Staff.assigned_location_id.in_(location_ids)
            ).all()
            site_director_staff_ids = [staff_id for (staff_id,) in site_director_ids]
            
            # Combine: coworkers + site directors + self
            all_visible_ids = set(coworker_staff_ids + site_director_staff_ids + [current_user.id])
            query = query.filter(Staff.id.in_(all_visible_ids))
        else:
            # No shift assignments - only see self
            query = query.filter(Staff.id == current_user.id)
    # Admin sees everyone (no filter)
    
    rows = query.all()
    
    return [
        StaffOut(
            id=s.id,
            first_name=s.first_name,
            middle_name=s.middle_name,
            last_name=s.last_name,
            preferred_name=s.preferred_name,
            suffix=s.suffix,
            work_email=s.work_email,
            work_phone=s.work_phone,
            role_id=s.role_id,
            role_name=role_name,
            assigned_location_id=s.assigned_location_id,
            profile_image_path=s.profile_image_path,
            is_active=s.is_active,
        )
        for s, role_name in rows
    ]


## STAFF ROLES (must come before /{staff_id})

@router.get("/roles", response_model=list[StaffRoleOut])
def get_all_roles(db: Session = Depends(get_db)):
    """Get all staff roles"""
    return db.query(StaffRole).all()


@router.get("/roles/{role_id}", response_model=StaffRoleOut)
def get_role_by_id(role_id: int, db: Session = Depends(get_db)):
    """Get a specific staff role by ID"""
    return get_or_404(db, StaffRole, role_id, detail=f"Role with id {role_id} not found")


@router.post("/roles", response_model=StaffRoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    role_data: StaffRoleCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Create a new staff role. Requires admin role."""
    new_role = StaffRole(**role_data.model_dump())
    
    try:
        db.add(new_role)
        db.commit()
        db.refresh(new_role)
        return new_role
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Role with this name already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/roles/{role_id}", response_model=StaffRoleOut)
def update_role(
    role_id: int,
    role_data: StaffRoleUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Update a staff role. Requires admin role."""
    role = get_or_404(db, StaffRole, role_id, detail=f"Role with id {role_id} not found")
    
    # Update only provided fields
    for key, value in role_data.model_dump(exclude_unset=True).items():
        setattr(role, key, value)
    
    try:
        db.commit()
        db.refresh(role)
        return role
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Role name already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/roles/{role_id}")
def deactivate_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Deactivate a staff role (soft-delete for HIPAA compliance). Requires admin role."""
    role = get_or_404(db, StaffRole, role_id, detail=f"Role with id {role_id} not found")
    
    if not role.is_active:
        raise HTTPException(status_code=400, detail="Role is already inactive")
    
    # Prevent deactivating core roles that are in use
    active_staff_count = db.query(Staff).filter(
        Staff.role_id == role_id,
        Staff.is_active == True
    ).count()
    
    if active_staff_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot deactivate role: {active_staff_count} active staff member(s) have this role"
        )
    
    role.is_active = False
    db.commit()
    return {"message": f"Role '{role.role_name}' deactivated"}


## STAFF MEMBERS

@router.get("/{staff_id}", response_model=StaffOut)
def get_staff_by_id(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get a specific staff member by ID.
    Role hierarchy enforced: users can only view staff at their level or below.
    Exception: users can always view their own profile.
    """
    row = (
        db.query(Staff, StaffRole.role_name)
        .join(StaffRole, Staff.role_id == StaffRole.id)
        .filter(Staff.id == staff_id)
        .first()
    )
    
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Staff member with id {staff_id} not found"
        )
    
    staff, role_name = row
    
    # Role hierarchy check: can only view staff at same level or below
    # Exception: users can always view their own profile
    if staff_id != current_user.id:
        # role_id is hierarchical: Admin(1) > Director(2) > Site Director(3) > DSP(4)
        # Lower role_id = higher privilege, so user can only see staff with >= their role_id
        if staff.role_id < current_user.role_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: cannot view staff members above your role level"
            )
    
    return StaffOut(
        id=staff.id,
        first_name=staff.first_name,
        middle_name=staff.middle_name,
        last_name=staff.last_name,
        preferred_name=staff.preferred_name,
        suffix=staff.suffix,
        work_email=staff.work_email,
        work_phone=staff.work_phone,
        role_id=staff.role_id,
        role_name=role_name,
        assigned_location_id=staff.assigned_location_id,
        profile_image_path=staff.profile_image_path,
        is_active=staff.is_active,
    )


@router.post("", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def create_staff(
    staff_data: StaffCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Create a new staff member. Requires admin role."""
    # Verify role exists
    role = db.query(StaffRole).filter(StaffRole.id == staff_data.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with id {staff_data.role_id} does not exist"
        )
    
    # Hash password
    password_hash = bcrypt.hashpw(
        staff_data.password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    # Create staff record (SQLAlchemy model for DB insertion)
    staff_dict = staff_data.model_dump(exclude={'password'})
    new_staff = Staff(
        **staff_dict,
        password_hash=password_hash,
        must_change_password=True,
        profile_image_path="placeholder.jpg"
    )
    
    # save to database using SQLAlchemy
    try:
        db.add(new_staff)
        db.commit()
        db.refresh(new_staff)
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Staff member with this email already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")
    
    # return Pydantic schema (FastAPI auto-converts)
    return StaffOut(
        id=new_staff.id,
        first_name=new_staff.first_name,
        middle_name=new_staff.middle_name,
        last_name=new_staff.last_name,
        preferred_name=new_staff.preferred_name,
        suffix=new_staff.suffix,
        work_email=new_staff.work_email,
        work_phone=new_staff.work_phone,
        role_id=new_staff.role_id,
        role_name=role.role_name,
        assigned_location_id=new_staff.assigned_location_id,
        profile_image_path=new_staff.profile_image_path,
        is_active=new_staff.is_active,
    )


@router.put("/{staff_id}", response_model=StaffOut)
def update_staff(
    staff_id: int,
    staff_data: StaffUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Update a staff member. Requires admin role."""
    staff = get_or_404(db, Staff, staff_id, detail=f"Staff member with id {staff_id} not found")
        
    # Update only provided fields
    for key, value in staff_data.model_dump(exclude_unset=True).items():
        setattr(staff, key, value)
    
    try:
        db.commit()
        db.refresh(staff)
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Staff member already exists")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Invalid reference (role_id)")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")
    
    # Get role name for response
    role = db.query(StaffRole).filter(StaffRole.id == staff.role_id).first()
    
    return StaffOut(
        id=staff.id,
        first_name=staff.first_name,
        middle_name=staff.middle_name,
        last_name=staff.last_name,
        preferred_name=staff.preferred_name,
        suffix=staff.suffix,
        work_email=staff.work_email,
        work_phone=staff.work_phone,
        role_id=staff.role_id,
        role_name=role.role_name if role else None,
        assigned_location_id=staff.assigned_location_id,
        profile_image_path=staff.profile_image_path,
        is_active=staff.is_active,
    )


from schemas import StaffResetPassword

@router.post("/{staff_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_staff_password(
    staff_id: int,
    payload: StaffResetPassword,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Admin-only: Reset a staff member's password to a temporary one.
    Forces the user to change it on next login.
    """
    from services.audit import AuditService
    
    staff = get_or_404(db, Staff, staff_id, detail=f"Staff member with id {staff_id} not found")
    
    # Validate password strength for the temporary password too
    validate_password_strength(payload.password)
    
    # Hash the new temporary password
    password_hash = bcrypt.hashpw(
        payload.password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')
    
    staff.password_hash = password_hash
    staff.must_change_password = True
    
    # Log security event for admin password reset
    audit = AuditService(
        db=db,
        user_id=current_user.id,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=request.headers.get("user-agent")
    )
    audit.log_security_event(
        event_type="admin_password_reset",
        severity="warning",
        description=f"Admin {current_user.id} reset password for staff {staff_id}",
        additional_data={"target_staff_id": staff_id}
    )
    
    db.commit()
    return


@router.delete("/{staff_id}")
def deactivate_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Deactivate a staff member (soft-delete for HIPAA compliance). Requires admin role.
    Also removes any future shift assignments for this staff member.
    """
    from models import Shift, ShiftAssignment
    from datetime import date
    
    staff = get_or_404(db, Staff, staff_id, detail=f"Staff member with id {staff_id} not found")
    
    if staff_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    
    if not staff.is_active:
        raise HTTPException(status_code=400, detail="Staff member is already inactive")
    
    # Count and remove future shift assignments
    future_assignments = db.query(ShiftAssignment).join(
        Shift, ShiftAssignment.shift_id == Shift.id
    ).filter(
        ShiftAssignment.staff_id == staff_id,
        Shift.start_date > date.today()
    ).all()
    
    removed_count = len(future_assignments)
    for assignment in future_assignments:
        db.delete(assignment)
    
    staff.is_active = False
    db.commit()
    
    message = f"Staff member {staff.first_name} {staff.last_name} deactivated"
    if removed_count > 0:
        message += f" and removed from {removed_count} future shift assignment(s)"
    
    return {"message": message, "removed_assignments": removed_count}


# =============================================
# PROFILE IMAGE UPLOAD
# =============================================
from fastapi import UploadFile, File
import os
import uuid

UPLOAD_DIR = "uploads/staff"

@router.post("/{staff_id}/profile-image")
async def upload_profile_image(
    staff_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Upload a profile image for a staff member. Requires admin role."""
    staff = get_or_404(db, Staff, staff_id, detail="Staff not found")
    
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Only JPG/JPEG images are allowed")
    
    # Create unique filename
    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"{staff_id}_{uuid.uuid4().hex[:8]}.{ext}"
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Delete old image if exists
    if staff.profile_image_path:
        old_path = os.path.join(UPLOAD_DIR, staff.profile_image_path)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    # Save new image
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Update database
    staff.profile_image_path = filename
    db.commit()
    
    return {"message": "Profile image uploaded successfully", "filename": filename}
