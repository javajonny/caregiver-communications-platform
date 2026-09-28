from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from authentication import get_current_active_user
from authorization import require_roles, ROLE_ADMIN, ROLE_DSP, ROLE_SITE_DIRECTOR, ROLE_DIRECTOR
from database import get_db
from models import (
    BehaviorType, BehaviorTrackingRecord,
    ClientUpdate, Staff, ClientProgramEnrollment,
    ShiftAssignment, ShiftPosition, ShiftPositionClient, Shift
)
from schemas import (
    BehaviorTypeCreate, BehaviorTypeUpdate, BehaviorTypeOut,
    BehaviorTrackingRecordCreate, BehaviorTrackingRecordOut,
    ClientUpdateCreate, ClientUpdateOut
)
from utils import get_or_404

router = APIRouter(
    tags=["Behaviors, Protocols & Documents"],
    dependencies=[Depends(get_current_active_user)]
)


# =============================================
# BEHAVIOR TYPES
# =============================================

@router.get("/behavior-types", response_model=list[BehaviorTypeOut])
def get_behavior_types(db: Session = Depends(get_db)):
    """Get all behavior types"""
    return db.query(BehaviorType).all()


@router.post("/behavior-types", response_model=BehaviorTypeOut, status_code=status.HTTP_201_CREATED)
def create_behavior_type(
    data: BehaviorTypeCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Create a new behavior type. Admin/Director only."""
    try:
        new_type = BehaviorType(**data.model_dump())
        db.add(new_type)
        db.commit()
        db.refresh(new_type)
        return new_type
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Behavior type already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/behavior-types/{type_id}", response_model=BehaviorTypeOut)
def update_behavior_type(
    type_id: int,
    data: BehaviorTypeUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Update a behavior type. Admin/Director only."""
    behavior_type = get_or_404(db, BehaviorType, type_id, detail="Behavior type not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(behavior_type, key, value)
    
    try:
        db.commit()
        db.refresh(behavior_type)
        return behavior_type
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Behavior type already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/behavior-types/{type_id}")
def deactivate_behavior_type(
    type_id: int, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Deactivate a behavior type (soft-delete). Admin/Director only for HIPAA compliance."""
    behavior_type = get_or_404(db, BehaviorType, type_id, detail="Behavior type not found")
    
    if not behavior_type.is_active:
        raise HTTPException(status_code=400, detail="Behavior type is already inactive")
    
    behavior_type.is_active = False
    db.commit()
    return {"message": f"Behavior type {type_id} deactivated"}



# =============================================
# BEHAVIOR TRACKING RECORDS
# =============================================

@router.get("/behavior-tracking", response_model=list[BehaviorTrackingRecordOut])
def get_behavior_tracking_records(
    request: Request,
    client_id: int = None, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all behavior tracking records, optionally filtered by client_id"""
    from services.audit import AuditService
    
    query = db.query(BehaviorTrackingRecord)
    
    # Role-based filtering
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # Site Directors: filter by location
        valid_client_ids = db.query(ClientProgramEnrollment.client_id).filter(
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).distinct()
        query = query.filter(BehaviorTrackingRecord.client_id.in_(valid_client_ids))
    elif current_user.role_id == ROLE_DSP:
        # DSP: filter by CURRENT shift assignment (today)
        from datetime import date
        today = date.today()
        
        assigned_client_ids = (
            db.query(ShiftPositionClient.client_id)
            .join(ShiftPosition, ShiftPositionClient.shift_position_id == ShiftPosition.id)
            .join(ShiftAssignment, ShiftAssignment.shift_position_id == ShiftPosition.id)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .filter(
                ShiftAssignment.staff_id == current_user.id,
                ShiftAssignment.ended_at.is_(None),
                Shift.start_date <= today,
                Shift.end_date >= today,
                Shift.cancelled_at.is_(None)
            )
            .distinct()
        )
        query = query.filter(BehaviorTrackingRecord.client_id.in_(assigned_client_ids))
    
    # Optional additional filter by specific client_id
    if client_id:
        query = query.filter(BehaviorTrackingRecord.client_id == client_id)
    
    records = query.all()
    
    # Log PHI access - behavior tracking records contain client health data
    client_ids = list(set(r.client_id for r in records))
    if client_ids:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read_list", "behavior_tracking_records", None, new_values={"record_ids": [r.id for r in records], "client_ids": client_ids})
        db.commit()
    
    return records


@router.post("/behavior-tracking", response_model=BehaviorTrackingRecordOut, status_code=status.HTTP_201_CREATED)
def create_behavior_tracking_record(
    data: BehaviorTrackingRecordCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Create a new behavior tracking record"""
    from services.audit import AuditService
    
    # HIPAA: Verify user has access to this client before creating records
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        has_access = db.query(ClientProgramEnrollment).filter(
            ClientProgramEnrollment.client_id == data.client_id,
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: client not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: check CURRENT shift assignment (today)
        from datetime import date
        today = date.today()
        
        has_access = (
            db.query(ShiftPositionClient)
            .join(ShiftPosition, ShiftPositionClient.shift_position_id == ShiftPosition.id)
            .join(ShiftAssignment, ShiftAssignment.shift_position_id == ShiftPosition.id)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .filter(
                ShiftPositionClient.client_id == data.client_id,
                ShiftAssignment.staff_id == current_user.id,
                ShiftAssignment.ended_at.is_(None),
                Shift.start_date <= today,
                Shift.end_date >= today,
                Shift.cancelled_at.is_(None)
            )
            .first()
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: client not assigned to your current shifts")
    
    try:
        new_record = BehaviorTrackingRecord(**data.model_dump())
        db.add(new_record)
        db.flush()
        
        # Log PHI creation - behavior tracking records contain client health data
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("create", "behavior_tracking_records", new_record.id, new_values={"client_id": new_record.client_id, "behavior_type_id": new_record.behavior_type_id})
        
        db.commit()
        db.refresh(new_record)
        return new_record
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Behavior tracking record already exists")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Invalid reference (shift_id, staff_id, client_id, or behavior_type_id)")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


# NOTE: PUT and DELETE endpoints for behavior-tracking have been intentionally
# removed for HIPAA compliance. Behavior tracking records are immutable after
# creation to maintain audit trail integrity. Records cannot be modified or deleted.



# =============================================
# CLIENT UPDATES
# Removed. Use clients.py endpoints instead.
# =============================================
