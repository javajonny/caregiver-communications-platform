from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from authentication import get_current_active_user
from authorization import require_roles, ROLE_ADMIN, ROLE_DIRECTOR, ROLE_SITE_DIRECTOR, ROLE_DSP
from database import get_db
from models import (
    Address, LocationType, ProgramLocation, ClientResidenceType, Staff, RelationshipType,
    Shift, ShiftAssignment, ShiftPosition, ShiftPositionClient, ClientResidenceHistory, ClientProgramEnrollment
)
from schemas import (
    AddressCreate, AddressUpdate, AddressOut,
    LocationTypeCreate, LocationTypeOut,
    ProgramLocationCreate, ProgramLocationUpdate, ProgramLocationOut
)
from utils import get_or_404

router = APIRouter(
    prefix="/locations",
    tags=["Locations"],
    dependencies=[Depends(get_current_active_user)]
)


# =============================================
# CLIENT RESIDENCE TYPES
# =============================================

@router.get("/residence-types")
def get_residence_types(db: Session = Depends(get_db)):
    """Get all client residence types"""
    return db.query(ClientResidenceType).all()


# =============================================
# RELATIONSHIP TYPES (for client contacts)
# =============================================

@router.get("/relationship-types")
def get_relationship_types(db: Session = Depends(get_db)):
    """Get all relationship types for client contacts"""
    return db.query(RelationshipType).all()


# =============================================
# ADDRESSES
# =============================================

def _get_allowed_address_ids(db: Session, current_user: Staff) -> list[int]:
    """
    Get address IDs the user is allowed to access based on their role.
    - Admin/Director: All addresses
    - Site Director: Program location address + client residence addresses at their location
    - DSP: Program location addresses where they work + client residence addresses for assigned clients
    """
    allowed_ids = set()
    
    if current_user.role_id in [ROLE_ADMIN, ROLE_DIRECTOR]:
        # Full access - return None to indicate no filtering needed
        return None
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # 1. Get program location address
        location = db.query(ProgramLocation).filter(
            ProgramLocation.id == current_user.assigned_location_id
        ).first()
        if location and location.address_id:
            allowed_ids.add(location.address_id)
        
        # 2. Get client residence addresses at their location
        client_ids = db.query(ClientProgramEnrollment.client_id).filter(
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).distinct()
        
        residence_addresses = db.query(ClientResidenceHistory.address_id).filter(
            ClientResidenceHistory.client_id.in_(client_ids),
            ClientResidenceHistory.address_id.isnot(None)
        ).distinct().all()
        
        for (addr_id,) in residence_addresses:
            allowed_ids.add(addr_id)
    
    elif current_user.role_id == ROLE_DSP:
        from datetime import date
        today = date.today()
        
        # 1. Get program location addresses where DSP has shifts
        location_ids = _get_dsp_location_ids(db, current_user.id)
        location_addresses = db.query(ProgramLocation.address_id).filter(
            ProgramLocation.id.in_(location_ids),
            ProgramLocation.address_id.isnot(None)
        ).all()
        for (addr_id,) in location_addresses:
            allowed_ids.add(addr_id)
        
        # 2. Get client residence addresses for clients assigned via current shifts
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
        
        residence_addresses = db.query(ClientResidenceHistory.address_id).filter(
            ClientResidenceHistory.client_id.in_(assigned_client_ids),
            ClientResidenceHistory.end_date.is_(None),  # Current residence only
            ClientResidenceHistory.address_id.isnot(None)
        ).distinct().all()
        
        for (addr_id,) in residence_addresses:
            allowed_ids.add(addr_id)
    
    return list(allowed_ids)


@router.get("/addresses", response_model=list[AddressOut])
def get_all_addresses(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get addresses scoped by role:
    - Admin/Director: All addresses
    - Site Director: Program location + client residences at their location
    - DSP: Work locations + current client residences for assigned clients
    """
    from services.audit import AuditService
    
    allowed_ids = _get_allowed_address_ids(db, current_user)
    
    if allowed_ids is None:
        # Admin/Director - full access
        addresses = db.query(Address).all()
    else:
        addresses = db.query(Address).filter(Address.id.in_(allowed_ids)).all()
    
    # Log potential PHI access (addresses may include client residences)
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "addresses", None, new_values={"address_ids": [a.id for a in addresses]})
    db.commit()
    
    return addresses


@router.get("/addresses/{address_id}", response_model=AddressOut)
def get_address(
    address_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get a specific address, scoped by role:
    - Admin/Director: Any address
    - Site Director: Only addresses at their location
    - DSP: Only addresses for their assigned clients/work locations
    """
    from services.audit import AuditService
    
    address = get_or_404(db, Address, address_id, detail="Address not found")
    
    # Check access
    allowed_ids = _get_allowed_address_ids(db, current_user)
    if allowed_ids is not None and address_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Access denied to this address")
    
    # Log potential PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "addresses", address_id)
    db.commit()
    
    return address


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(
    address_data: AddressCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Create a new address. If address exists, returns existing one."""
    from services.audit import AuditService
    # Check for existing address to avoid duplicates/errors
    existing_address = db.query(Address).filter(
        Address.street_line_1 == address_data.street_line_1,
        Address.street_line_2 == (address_data.street_line_2 or ""), # Handle None/Empty consistency
        Address.city == address_data.city,
        Address.state_province == address_data.state_province,
        Address.postal_code == address_data.postal_code,
        Address.country == (address_data.country or "USA")
    ).first()

    if existing_address:
        return existing_address

    new_address = Address(**address_data.model_dump())
    
    try:
        db.add(new_address)
        db.commit()
        db.refresh(new_address)
        
        # Log address creation
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("create", "addresses", new_address.id, new_values={"city": new_address.city, "state": new_address.state_province})
        db.commit()
        
        return new_address
    except IntegrityError as e:
        db.rollback()
        # Fallback check in case of race condition
        existing_check = db.query(Address).filter(
            Address.street_line_1 == address_data.street_line_1,
            Address.street_line_2 == (address_data.street_line_2 or ""),
            Address.city == address_data.city,
            Address.state_province == address_data.state_province,
            Address.postal_code == address_data.postal_code
        ).first()
        
        if existing_check:
            return existing_check
            
        if "duplicate key value violates unique constraint" in str(e.orig):
             raise HTTPException(status_code=409, detail="Address already exists")
        else: 
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(
    address_id: int,
    address_data: AddressUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Update an address. Requires admin or director role."""
    from services.audit import AuditService
    
    address = get_or_404(db, Address, address_id, detail="Address not found")
    
    # Capture old values for audit
    old_values = {"city": address.city, "state": address.state_province}
    
    for key, value in address_data.model_dump(exclude_unset=True).items():
        setattr(address, key, value)
    
    try:
        db.commit()
        db.refresh(address)
        
        # Log address update
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("update", "addresses", address_id, old_values=old_values, new_values={"city": address.city, "state": address.state_province})
        db.commit()
        
        return address
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Address already exists")
        else: 
            raise HTTPException(status_code=500, detail="An unexpected error occurred")



@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Delete an address. Requires admin or director role."""
    from services.audit import AuditService
    
    address = get_or_404(db, Address, address_id, detail="Address not found")
    
    # Capture values for audit before deletion
    old_values = {"city": address.city, "state": address.state_province}
    
    try:
        db.delete(address)
        
        # Log address deletion before commit
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("delete", "addresses", address_id, old_values=old_values)
        
        db.commit()
        return {"message": f"Address {address_id} deleted"}
    except IntegrityError as e:
        db.rollback()
        if "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Address cannot be deleted because it is in use")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


# =============================================
# LOCATION TYPES
# =============================================

@router.get("/types", response_model=list[LocationTypeOut])
def get_all_location_types(db: Session = Depends(get_db)):
    """Get all active location types"""
    return db.query(LocationType).filter(LocationType.is_active == True).all()


@router.get("/types/{type_id}", response_model=LocationTypeOut)
def get_location_type(type_id: int, db: Session = Depends(get_db)):
    """Get a specific location type"""
    loc_type = get_or_404(db, LocationType, type_id, detail="Location type not found")
    if not loc_type.is_active:
        raise HTTPException(status_code=404, detail="Location type not found")
    return loc_type


@router.post("/types", response_model=LocationTypeOut, status_code=status.HTTP_201_CREATED)
def create_location_type(data: LocationTypeCreate, db: Session = Depends(get_db), current_user: Staff = Depends(require_roles(["admin"]))):
    """Create a new location type. Requires admin role."""
    try: 
        new_type = LocationType(**data.model_dump())
        db.add(new_type)
        db.commit()
        db.refresh(new_type)
        return new_type
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            # This catches violation of uq_location_type_active_name (trying to create duplicate ACTIVE name)
            raise HTTPException(status_code=409, detail="Active location type with this name already exists")
        else: 
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/types/{type_id}")
def delete_location_type(type_id: int, db: Session = Depends(get_db), current_user: Staff = Depends(require_roles(["admin"]))):
    """Deactivate (soft delete) a location type. Requires admin role."""
    loc_type = get_or_404(db, LocationType, type_id, detail="Location type not found")
    
    # Check if in use by active program locations before deactivating
    # If we want to prevent deactivating types that are in use:
    active_usage = db.query(ProgramLocation).filter(
        ProgramLocation.location_type_id == type_id,
        ProgramLocation.is_active == True
    ).first()
    
    if active_usage:
        raise HTTPException(status_code=409, detail="Cannot deactivate location type; it is in use by active program locations")

    loc_type.is_active = False
    db.commit()
    return {"message": f"Location type {type_id} deactivated"}

# =============================================
# PROGRAM LOCATIONS
# =============================================

def _get_dsp_location_ids(db: Session, staff_id: int) -> list[int]:
    """Get location IDs where DSP has shift assignments (past, current, or future)."""
    location_ids = db.query(Shift.program_location_id).join(
        ShiftAssignment, ShiftAssignment.shift_id == Shift.id
    ).filter(
        ShiftAssignment.staff_id == staff_id,
        Shift.cancelled_at.is_(None)  # Only non-cancelled shifts
    ).distinct().all()
    return [loc_id for (loc_id,) in location_ids]


@router.get("/programs", response_model=list[ProgramLocationOut])
def get_all_program_locations(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get program locations scoped by role:
    - Admin/Director: All locations
    - Site Director: Only their assigned location
    - DSP: Only locations where they have shift assignments
    """
    query = db.query(ProgramLocation).options(joinedload(ProgramLocation.location_type))
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        query = query.filter(ProgramLocation.id == current_user.assigned_location_id)
    elif current_user.role_id == ROLE_DSP:
        allowed_location_ids = _get_dsp_location_ids(db, current_user.id)
        query = query.filter(ProgramLocation.id.in_(allowed_location_ids))
        
    return query.all()


@router.get("/programs/{program_id}", response_model=ProgramLocationOut)
def get_program_location(
    program_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get a specific program location, scoped by role:
    - Admin/Director: Any location
    - Site Director: Only their assigned location
    - DSP: Only locations where they have shift assignments
    """
    location = get_or_404(db, ProgramLocation, program_id, detail="Program location not found")
    
    # Check access based on role
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != program_id:
            raise HTTPException(status_code=403, detail="Access denied to this location")
    elif current_user.role_id == ROLE_DSP:
        allowed_location_ids = _get_dsp_location_ids(db, current_user.id)
        if program_id not in allowed_location_ids:
            raise HTTPException(status_code=403, detail="Access denied to this location")
    
    return location


@router.post("/programs", response_model=ProgramLocationOut, status_code=status.HTTP_201_CREATED)
def create_program_location(data: ProgramLocationCreate, db: Session = Depends(get_db), current_user: Staff = Depends(require_roles(["admin"]))):
    """Create a new program location. Requires admin role."""

    # check if location_type_id and address_id exist
    location_type = db.query(LocationType).filter(LocationType.id == data.location_type_id).first()
    if not location_type:
        raise HTTPException(status_code=400, detail="Invalid location_type_id")
    
    if data.address_id is None:
        raise HTTPException(status_code=400, detail="Address is required for program locations")
    
    address = db.query(Address).filter(Address.id == data.address_id).first()
    if not address:
        raise HTTPException(status_code=400, detail="Invalid address_id")

    try:
        new_program = ProgramLocation(**data.model_dump())
        db.add(new_program)
        db.commit()
        db.refresh(new_program)
        return new_program
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Program location already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")



@router.put("/programs/{program_id}", response_model=ProgramLocationOut)
def update_program_location(program_id: int, data: ProgramLocationUpdate, db: Session = Depends(get_db), current_user: Staff = Depends(require_roles(["admin"]))):
    """Update a program location. Requires admin role."""
    program = get_or_404(db, ProgramLocation, program_id, detail="Program location not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(program, key, value)
    
    try: 
        db.commit()
        db.refresh(program)
        return program
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Program location already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")



@router.delete("/programs/{program_id}")
def delete_program_location(program_id: int, db: Session = Depends(get_db), current_user: Staff = Depends(require_roles(["admin"]))):
    """Delete a program location. Requires admin role."""
    program = get_or_404(db, ProgramLocation, program_id, detail="Program location not found")
    
    try:
        db.delete(program)
        db.commit()
        return {"message": f"Program location {program_id} deleted"}
    except IntegrityError as e:
        db.rollback()
        if "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Cannot delete program location; it is in use")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")