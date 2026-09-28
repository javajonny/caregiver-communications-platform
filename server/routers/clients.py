from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from authentication import get_current_active_user
from authorization import require_roles
from database import get_db
from models import (
    Client, ClientContact, ClientResidenceHistory,
    ClientProgramEnrollment, ProgramLocation, Staff,
    ClientDocument, ClientDocumentAuditLog, DocumentTemplate,
    ClientUpdate as ClientUpdateModel, ClientUpdateRead, BehaviorTrackingRecord,
    BehaviorType, ClientBehaviorConfigVersion, ClientBehaviorConfigItem,
    ShiftAssignment, ShiftPosition, ShiftPositionClient, Shift
)
from schemas import (
    ClientCreate, ClientUpdate, ClientOut,
    ClientContactCreate, ClientContactUpdate, ClientContactOut,
    ClientResidenceHistoryCreate, ClientResidenceHistoryUpdate, ClientResidenceHistoryOut,
    ClientProgramEnrollmentCreate, ClientProgramEnrollmentUpdate, ClientProgramEnrollmentOut,
    ClientDocumentCreate, BehaviorTrackingRecordWithDetails,
    BehaviorTypeOut, ConfigVersionOut, ConfigVersionCreate
)
from utils import get_or_404
from authorization import ROLE_ADMIN, ROLE_DIRECTOR, ROLE_SITE_DIRECTOR, ROLE_DSP


router = APIRouter(
    prefix="/clients",
    tags=["Clients"],
    dependencies=[Depends(get_current_active_user)]
)


# =============================================
# CLIENTS
# =============================================

UPLOAD_DIR = "uploads/clients"


def _check_client_access(db: Session, current_user: Staff, client_id: int) -> None:
    """
    HIPAA Minimum Necessary: Verify user has access to this client.
    - Admin/Director: Full access
    - Site Director: Only clients enrolled at their assigned location
    - DSP: Only clients assigned to them via active shift assignments
    
    Raises HTTPException 403 if access denied.
    """
    # Admin and Director have full access
    if current_user.role_id in [ROLE_ADMIN, ROLE_DIRECTOR]:
        return
    
    # Site Directors: Check location-based access
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        has_access = db.query(ClientProgramEnrollment).filter(
            ClientProgramEnrollment.client_id == client_id,
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: client not at your location")
        return
    
    # DSP: Check shift-based access (only CURRENT shifts - happening today)
    if current_user.role_id == ROLE_DSP:
        from datetime import date
        today = date.today()
        
        has_access = (
            db.query(ShiftPositionClient)
            .join(ShiftPosition, ShiftPositionClient.shift_position_id == ShiftPosition.id)
            .join(ShiftAssignment, ShiftAssignment.shift_position_id == ShiftPosition.id)
            .join(Shift, ShiftAssignment.shift_id == Shift.id)
            .filter(
                ShiftPositionClient.client_id == client_id,
                ShiftAssignment.staff_id == current_user.id,
                ShiftAssignment.ended_at.is_(None),
                # Shift must be happening today
                Shift.start_date <= today,
                Shift.end_date >= today,
                Shift.cancelled_at.is_(None)
            )
            .first()
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: client not assigned to your current shifts")
        return



@router.get("", response_model=list[ClientOut])
def get_all_clients(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all clients. Site Directors only see clients at their assigned location."""
    from services.audit import AuditService
    
    query = db.query(Client).options(joinedload(Client.program_enrollments))
    
    # Site Directors only see clients enrolled at their assigned location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        client_ids = db.query(ClientProgramEnrollment.client_id).filter(
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).distinct()
        query = query.filter(Client.id.in_(client_ids))
    
    # DSP: Only see clients assigned to them via CURRENT shift assignments
    # This enforces HIPAA Minimum Necessary at the data layer
    elif current_user.role_id == ROLE_DSP:
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
                # Shift must be happening today
                Shift.start_date <= today,
                Shift.end_date >= today,
                Shift.cancelled_at.is_(None)
            )
            .distinct()
        )
        query = query.filter(Client.id.in_(assigned_client_ids))
    
    clients = query.all()
    
    # Log PHI access (access to client list)
    audit = AuditService(
        db=db,
        user_id=current_user.id,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=request.headers.get("user-agent")
    )
    audit.log_data_access(
        "read_list", "clients", None,
        new_values={
            "count": len(clients),
            "client_ids": [c.id for c in clients]
        }
    )
    db.commit()
    
    return clients


# Static route MUST be before parameterized routes to avoid matching "behavior-types" as client_id
@router.get("/behavior-types", response_model=list[BehaviorTypeOut])
def get_behavior_types(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all available behavior types."""
    return db.query(BehaviorType).filter(BehaviorType.is_active == True).all()


# Import here to avoid circular imports
from models import (
    DocumentCategory, DocumentSubcategory, DocumentTemplate, 
    ClientDocument, ClientDocumentAuditLog, Staff
)
# Import here to avoid circular imports
from models import (
    DocumentCategory, DocumentSubcategory, DocumentTemplate, 
    ClientDocument, ClientDocumentAuditLog, Staff
)
from pydantic import BaseModel
from typing import Optional, Any
from datetime import date
from fastapi import UploadFile, File
import os
import uuid

class DocumentTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: str
    version: int
    form_schema: dict
    
    class Config:
        from_attributes = True


class ClientDocumentResponse(BaseModel):
    id: int
    client_id: int
    template_id: int
    template_name: str
    template_icon: str
    template_version: int
    subcategory_id: Optional[int]
    subcategory_name: Optional[str]
    revision_interval_days: int
    created_at: Optional[str]
    created_by_name: Optional[str]
    last_reviewed_at: Optional[str]
    last_reviewed_by_name: Optional[str]
    last_review_changes_made: Optional[bool]
    review_count: int
    form_schema: dict
    values: dict
    is_current: bool

    class Config:
        from_attributes = True



@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    request: "Request",
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get a specific client. Access is scoped by role."""
    from fastapi import Request
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    # Log PHI access
    audit = AuditService(
        db=db,
        user_id=current_user.id,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=request.headers.get("user-agent")
    )
    audit.log_data_access("read", "clients", client_id)
    db.commit()
    
    return client


@router.post("/{client_id}/profile-image")
async def upload_profile_image(
    client_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Upload a profile image for a client."""
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id, detail="Client not found")
    old_image = client.profile_image_path
    
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/jpg"]:
        raise HTTPException(status_code=400, detail="Only JPG/JPEG images are allowed")
    
    # Create unique filename
    ext = file.filename.split(".")[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"{uuid.uuid4()}.{ext}"
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
            
    # Update client record
    client.profile_image_path = filename
    
    # Log PHI access (profile image is PHI)
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("update", "clients", client_id, old_values={"profile_image_path": old_image}, new_values={"profile_image_path": filename})
    
    db.commit()
    db.refresh(client)
    
    return {"filename": filename, "url": f"/uploads/clients/{filename}"}


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    request: "Request",
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Create a new client. Requires admin role."""
    from fastapi import Request
    from services.audit import AuditService
    
    try:
        client_data = data.model_dump()
        client_data["profile_image_path"] = "placeholder.jpg"
        new_client = Client(**client_data)
        db.add(new_client)
        db.flush()  # Get ID before commit
        
        # Log PHI creation
        audit = AuditService(
            db=db,
            user_id=current_user.id,
            ip=getattr(request.state, 'client_ip', None),
            user_agent=request.headers.get("user-agent")
        )
        audit.log_data_access(
            "create", "clients", new_client.id,
            new_values={"first_name": new_client.first_name, "last_name": new_client.last_name}
        )
        
        db.commit()
        db.refresh(new_client)
        return new_client
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")
        

@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    data: ClientUpdate,
    request: "Request",
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Update a client. Requires admin role."""
    from fastapi import Request
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id, detail="Client not found")
    
    # Capture old values for audit
    old_values = {k: getattr(client, k) for k in data.model_dump(exclude_unset=True).keys()}

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)

    try:
        # Log PHI update
        audit = AuditService(
            db=db,
            user_id=current_user.id,
            ip=getattr(request.state, 'client_ip', None),
            user_agent=request.headers.get("user-agent")
        )
        audit.log_data_access(
            "update", "clients", client_id,
            old_values=old_values,
            new_values=data.model_dump(exclude_unset=True)
        )
        
        db.commit()
        db.refresh(client)
        return client
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/{client_id}")
def deactivate_client(
    client_id: int,
    request: "Request",
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Deactivate a client (soft-delete for HIPAA compliance). Requires admin role."""
    from fastapi import Request
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id, detail="Client not found")
    
    if not client.is_active:
        raise HTTPException(status_code=400, detail="Client is already inactive")
    
    client.is_active = False
    
    # Log PHI deactivation
    audit = AuditService(
        db=db,
        user_id=current_user.id,
        ip=getattr(request.state, 'client_ip', None),
        user_agent=request.headers.get("user-agent")
    )
    audit.log_data_access(
        "delete", "clients", client_id,
        old_values={"is_active": True},
        new_values={"is_active": False}
    )
    
    db.commit()
    return {"message": f"Client {client_id} deactivated"}


# =============================================
# CLIENT CONTACTS
# =============================================

@router.get("/{client_id}/contacts", response_model=list[ClientContactOut])
def get_client_contacts(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all contacts for a client"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    contacts = db.query(ClientContact).options(
        joinedload(ClientContact.address)
    ).filter(ClientContact.client_id == client_id).all()
    
    # Log PHI access - include specific contact IDs
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_contacts", None, new_values={"client_id": client_id, "contact_ids": [c.id for c in contacts]})
    db.commit()
    
    return contacts


#get specific contact for a client
@router.get("/contacts/{contact_id}", response_model=ClientContactOut)
def get_client_contact(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get a specific contact by ID"""
    from services.audit import AuditService
    
    contact = db.query(ClientContact).options(
        joinedload(ClientContact.address)
    ).filter(ClientContact.id == contact_id).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # HIPAA: Check access to the client this contact belongs to
    _check_client_access(db, current_user, contact.client_id)
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "client_contacts", contact_id)
    db.commit()
    
    return contact


@router.post("/contacts", response_model=ClientContactOut, status_code=status.HTTP_201_CREATED)
def create_client_contact(
    data: ClientContactCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Create a new contact for a client"""
    from services.audit import AuditService
    
    # HIPAA: Check access to the client before creating contact
    _check_client_access(db, current_user, data.client_id)
    
    try:
        new_contact = ClientContact(**data.model_dump())
        db.add(new_contact)
        db.flush()
        
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("create", "client_contacts", new_contact.id, new_values={"client_id": data.client_id})
        
        db.commit()
        db.refresh(new_contact)
        new_contact = db.query(ClientContact).options(
            joinedload(ClientContact.address)
        ).filter(ClientContact.id == new_contact.id).first()
        return new_contact
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Referenced record does not exist")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/contacts/{contact_id}", response_model=ClientContactOut)
def update_client_contact(
    contact_id: int,
    data: ClientContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Update a client contact"""
    from services.audit import AuditService
    
    contact = get_or_404(db, ClientContact, contact_id, detail="Contact not found")
    
    # HIPAA: Check access to the client this contact belongs to
    _check_client_access(db, current_user, contact.client_id)
    old_values = {k: getattr(contact, k) for k in data.model_dump(exclude_unset=True).keys()}
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    
    try:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("update", "client_contacts", contact_id, old_values=old_values, new_values=data.model_dump(exclude_unset=True))
        
        db.commit()
        db.refresh(contact)
        contact = db.query(ClientContact).options(
            joinedload(ClientContact.address)
        ).filter(ClientContact.id == contact.id).first()
        return contact
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Referenced record does not exist")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/contacts/{contact_id}")
def deactivate_client_contact(
    contact_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Deactivate a client contact (soft-delete for HIPAA compliance)"""
    from services.audit import AuditService
    
    contact = get_or_404(db, ClientContact, contact_id, detail="Contact not found")
    
    # HIPAA: Check access to the client this contact belongs to
    _check_client_access(db, current_user, contact.client_id)
    
    if not contact.is_active:
        raise HTTPException(status_code=400, detail="Contact is already inactive")
    
    contact.is_active = False
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("delete", "client_contacts", contact_id, old_values={"is_active": True}, new_values={"is_active": False})
    
    db.commit()
    return {"message": f"Contact {contact_id} deactivated"}


# =============================================
# CLIENT RESIDENCE HISTORY
# =============================================
@router.get("/{client_id}/residence", response_model=ClientResidenceHistoryOut)
def get_client_current_residence(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get current residence for a client (where end_date is NULL)"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    residence = db.query(ClientResidenceHistory).options(
        joinedload(ClientResidenceHistory.address),
        joinedload(ClientResidenceHistory.residence_type)
    ).filter(
        ClientResidenceHistory.client_id == client_id,
        ClientResidenceHistory.end_date == None,
        (ClientResidenceHistory.end_status == None) | (ClientResidenceHistory.end_status != 'cancelled')
    ).first()
    
    if not residence:
        raise HTTPException(status_code=404, detail="No current residence found for this client")
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "client_residence_history", residence.id)
    db.commit()
    
    return residence


@router.get("/{client_id}/residence/history", response_model=list[ClientResidenceHistoryOut])
def get_client_residence_history(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get full residence history for a client (all past and current residences)"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    history = db.query(ClientResidenceHistory).filter(
        ClientResidenceHistory.client_id == client_id
    ).order_by(ClientResidenceHistory.start_date.desc()).all()
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_residence_history", None, new_values={"client_id": client_id, "residence_ids": [h.id for h in history]})
    db.commit()
    
    return history


@router.post("/residence", response_model=ClientResidenceHistoryOut, status_code=status.HTTP_201_CREATED)
def create_client_residence(
    data: ClientResidenceHistoryCreate,
    request: Request,
    db: Session = Depends(get_db), 
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Create new residence record for a client. Automatically ends any current residence. Requires admin or director role."""
    from datetime import date as date_type
    from services.audit import AuditService
    
    current_residence = db.query(ClientResidenceHistory).filter(
        ClientResidenceHistory.client_id == data.client_id,
        ClientResidenceHistory.end_date == None
    ).first()
    
    if current_residence:
        from datetime import datetime as datetime_type
        current_residence.end_date = data.start_date
        current_residence.ended_by = current_user.id
        current_residence.ended_at = datetime_type.now()
    
    try:
        new_residence = ClientResidenceHistory(
            **data.model_dump(),
            created_by=current_user.id
        )
        db.add(new_residence)
        db.flush()
        
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("create", "client_residence_history", new_residence.id, new_values={"client_id": data.client_id})
        
        db.commit()
        db.refresh(new_residence)
        new_residence = db.query(ClientResidenceHistory).options(
            joinedload(ClientResidenceHistory.address),
            joinedload(ClientResidenceHistory.residence_type)
        ).filter(ClientResidenceHistory.id == new_residence.id).first()
        return new_residence
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A residence record with this start date already exists")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Referenced record does not exist")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/{client_id}/residence/{residence_id}", response_model=ClientResidenceHistoryOut)
def update_client_residence(
    client_id: int,
    residence_id: int,
    data: ClientResidenceHistoryUpdate, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """
    DISABLED: Editing residence records is not allowed for HIPAA compliance.
    Residence history is immutable once created. To correct errors, end the current
    residence and create a new one with the correct information.
    """
    raise HTTPException(
        status_code=403, 
        detail="Editing residence records is disabled for HIPAA compliance. End the current residence and create a new one instead."
    )


@router.delete("/{client_id}/residence")
def end_client_residence(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """End current residence for a client (sets end_date to today). HIPAA-compliant soft delete. Requires admin or director role."""
    from datetime import date as date_type
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    
    residence = db.query(ClientResidenceHistory).filter(
        ClientResidenceHistory.client_id == client_id,
        ClientResidenceHistory.end_date == None
    ).first()
    
    if not residence:
        raise HTTPException(status_code=404, detail="No current residence found for this client")
    
    today = date_type.today()
    
    if residence.start_date > today:
        residence.end_date = today
        residence.end_status = "cancelled"
        msg = f"Future residence scheduled for {residence.start_date} has been cancelled."
    else:
        residence.end_date = today
        residence.end_status = "completed"
        msg = f"Residence ended for client {client_id}"

    residence.ended_by = current_user.id
    residence.ended_at = datetime.now()
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("delete", "client_residence_history", residence.id, old_values={"end_date": None}, new_values={"end_date": str(today), "end_status": residence.end_status})
    
    db.commit()
    return {"message": msg}


# =============================================
# CLIENT PROGRAM ENROLLMENTS
# =============================================

@router.get("/{client_id}/enrollments", response_model=list[ClientProgramEnrollmentOut])
def get_client_enrollments(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all program enrollments for a client"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    enrollments = db.query(ClientProgramEnrollment).filter(ClientProgramEnrollment.client_id == client_id).all()
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_program_enrollments", None, new_values={"client_id": client_id, "enrollment_ids": [e.id for e in enrollments]})
    db.commit()
    
    return enrollments


@router.post("/enrollments", response_model=ClientProgramEnrollmentOut, status_code=status.HTTP_201_CREATED)
def create_client_enrollment(
    data: ClientProgramEnrollmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Create a new program enrollment for a client. Requires admin or director role."""
    from services.audit import AuditService
    
    try:
        new_enrollment = ClientProgramEnrollment(
            **data.model_dump(),
            created_by=current_user.id
        )
        db.add(new_enrollment)
        db.flush()
        
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("create", "client_program_enrollments", new_enrollment.id, new_values={"client_id": data.client_id, "program_location_id": data.program_location_id})
        
        db.commit()
        db.refresh(new_enrollment)
        return new_enrollment
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig) or "idx_enrollment_active" in str(e.orig):
            raise HTTPException(status_code=409, detail="Client is already enrolled at this location")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Referenced record does not exist")
        elif "violates check constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Data violates a table constraint")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/enrollments/{enrollment_id}", response_model=ClientProgramEnrollmentOut)
def update_client_enrollment(enrollment_id: int, data: ClientProgramEnrollmentUpdate, db: Session = Depends(get_db), current_user: Staff = Depends(require_roles(["admin"]))):
    """
    DISABLED: Editing enrollment records is not allowed for HIPAA compliance.
    Enrollment history is immutable once created. To correct errors, end the current
    enrollment and create a new one with the correct information.
    """
    raise HTTPException(
        status_code=403, 
        detail="Editing enrollment records is disabled for HIPAA compliance. End the current enrollment and create a new one instead."
    )


@router.delete("/enrollments/{enrollment_id}")
def end_client_enrollment(
    enrollment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """End a client enrollment (sets end_date to today). HIPAA-compliant soft delete. Requires admin or director role."""
    from services.audit import AuditService
    
    enrollment = get_or_404(db, ClientProgramEnrollment, enrollment_id, detail="Enrollment not found")
    
    if enrollment.end_date is not None:
        raise HTTPException(status_code=400, detail="Enrollment has already ended")

    from datetime import date as date_type
    today = date_type.today()

    if enrollment.start_date > today:
        enrollment.end_date = today
        enrollment.end_status = "cancelled"
        msg = f"Future enrollment scheduled for {enrollment.start_date} has been cancelled."
    else:
        enrollment.end_date = today
        enrollment.end_status = "completed"
        msg = f"Enrollment ended for client."

    enrollment.ended_by = current_user.id
    enrollment.ended_at = datetime.now()
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("delete", "client_program_enrollments", enrollment_id, old_values={"end_date": None}, new_values={"end_date": str(today), "end_status": enrollment.end_status})
    
    db.commit()
    return {"message": msg}


# =============================================
# CLIENT UPDATES
# =============================================

from models import ClientUpdate as ClientUpdateModel, ClientUpdateRead, Staff
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ClientUpdateCreate(BaseModel):
    content: str

class ClientUpdateOut(BaseModel):
    id: int
    client_id: int
    created_by: int
    content: str
    is_archived: bool
    created_at: datetime
    author_name: Optional[str] = None
    is_read: bool = False
    
    class Config:
        from_attributes = True


@router.get("/{client_id}/updates", response_model=list[ClientUpdateOut])
def get_client_updates(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all updates for a client (non-archived) with read status"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    updates = db.query(ClientUpdateModel, Staff).join(
        Staff, ClientUpdateModel.created_by == Staff.id
    ).filter(
        ClientUpdateModel.client_id == client_id,
        ClientUpdateModel.is_archived == False
    ).order_by(ClientUpdateModel.created_at.desc()).all()
    
    read_update_ids = set(
        r.update_id for r in db.query(ClientUpdateRead.update_id).filter(
            ClientUpdateRead.staff_id == current_user.id
        ).all()
    )
    
    result = []
    for update, staff in updates:
        is_read = update.id in read_update_ids or update.created_by == current_user.id
        
        result.append(ClientUpdateOut(
            id=update.id,
            client_id=update.client_id,
            created_by=update.created_by,
            content=update.content,
            is_archived=update.is_archived,
            created_at=update.created_at,
            author_name=f"{staff.first_name} {staff.last_name}",
            is_read=is_read
        ))
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_updates", None, new_values={"client_id": client_id, "update_ids": [u.id for u in result]})
    db.commit()
    
    return result



@router.get("/{client_id}/updates/count")
def get_client_updates_count(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get count of UNREAD updates for a client"""
    from sqlalchemy import and_, or_
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    # Get all non-archived updates for this client
    all_updates = db.query(ClientUpdateModel).filter(
        ClientUpdateModel.client_id == client_id,
        ClientUpdateModel.is_archived == False
    ).all()
    
    # Get updates read by current user
    read_update_ids = set(
        r.update_id for r in db.query(ClientUpdateRead.update_id).filter(
            ClientUpdateRead.staff_id == current_user.id
        ).all()
    )
    
    # Count unread (not read AND not created by current user)
    unread_count = sum(
        1 for u in all_updates 
        if u.id not in read_update_ids and u.created_by != current_user.id
    )
    
    # Log PHI access (accessing client update count is PHI access)
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "client_updates", None, new_values={"client_id": client_id, "unread_count": unread_count})
    db.commit()
    
    return {"count": unread_count}


@router.post("/{client_id}/updates", response_model=ClientUpdateOut, status_code=status.HTTP_201_CREATED)
def create_client_update(
    client_id: int,
    data: ClientUpdateCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Create a new update for a client (auto-marked as read by creator)"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    new_update = ClientUpdateModel(
        client_id=client_id,
        created_by=current_user.id,
        content=data.content.strip()
    )
    
    db.add(new_update)
    db.flush()
    
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("create", "client_updates", new_update.id, new_values={"client_id": client_id})
    
    db.commit()
    db.refresh(new_update)
    
    read_record = ClientUpdateRead(
        update_id=new_update.id,
        staff_id=current_user.id
    )
    db.add(read_record)
    db.commit()
    
    return ClientUpdateOut(
        id=new_update.id,
        client_id=new_update.client_id,
        created_by=new_update.created_by,
        content=new_update.content,
        is_archived=new_update.is_archived,
        created_at=new_update.created_at,
        author_name=f"{current_user.first_name} {current_user.last_name}",
        is_read=True
    )


@router.get("/{client_id}/updates/{update_id}", response_model=ClientUpdateOut)
def get_client_update(
    client_id: int,
    update_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get a specific update for a client"""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    update = get_or_404(db, ClientUpdateModel, update_id, detail="Update not found")
    
    if update.client_id != client_id:
        raise HTTPException(status_code=404, detail="Update not found for this client")
        
    staff = db.query(Staff).filter(Staff.id == update.created_by).first()
    author_name = f"{staff.first_name} {staff.last_name}" if staff else "Unknown"
    
    # Check read status
    is_read = db.query(ClientUpdateRead).filter(
        ClientUpdateRead.update_id == update_id,
        ClientUpdateRead.staff_id == current_user.id
    ).first() is not None or update.created_by == current_user.id

    # Log PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "client_updates", update.id, new_values={"client_id": client_id})
    db.commit()
    
    return ClientUpdateOut(
        id=update.id,
        client_id=update.client_id,
        created_by=update.created_by,
        content=update.content,
        is_archived=update.is_archived,
        created_at=update.created_at,
        author_name=author_name,
        is_read=is_read
    )


@router.delete("/{client_id}/updates/{update_id}")
def archive_client_update(
    client_id: int,
    update_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
    """Archive a client update (soft-delete). Admin only."""
    from services.audit import AuditService
    
    get_or_404(db, Client, client_id, detail="Client not found")
    update = get_or_404(db, ClientUpdateModel, update_id, detail="Update not found")
    
    if update.client_id != client_id:
        raise HTTPException(status_code=404, detail="Update not found for this client")
    
    if update.is_archived:
        raise HTTPException(status_code=400, detail="Update is already archived")
        
    update.is_archived = True
    
    # Log deletion/archival
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("delete", "client_updates", update.id, old_values={"is_archived": False}, new_values={"is_archived": True, "client_id": client_id})
    
    db.commit()
    return {"message": f"Update {update_id} archived"}


@router.post("/{client_id}/updates/{update_id}/read")
def mark_update_as_read(
    client_id: int,
    update_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Mark an update as read for the current user"""
    from services.audit import AuditService
    
    _check_client_access(db, current_user, client_id)
    
    # Check if update exists and belongs to client
    update = db.query(ClientUpdateModel).filter(
        ClientUpdateModel.id == update_id,
        ClientUpdateModel.client_id == client_id
    ).first()
    
    if not update:
        raise HTTPException(status_code=404, detail="Update not found")
    
    # Check if already read
    existing = db.query(ClientUpdateRead).filter(
        ClientUpdateRead.update_id == update_id,
        ClientUpdateRead.staff_id == current_user.id
    ).first()
    
    if not existing:
        read_record = ClientUpdateRead(
            update_id=update_id,
            staff_id=current_user.id
        )
        db.add(read_record)
        
        # Log PHI access (reading client update is PHI access)
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read", "client_updates", update_id, new_values={"client_id": client_id})
        
        db.commit()
    
    return {"message": "Update marked as read"}



class DocumentListItem(BaseModel):
    template_id: int
    template_name: str
    template_icon: str
    has_document: bool
    
    class Config:
        from_attributes = True


# =============================================
# CLIENT DOCUMENTS
# =============================================

@router.post("/{client_id}/documents", response_model=ClientDocumentResponse, status_code=status.HTTP_201_CREATED)
def create_client_document(
    client_id: int,
    data: ClientDocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new document for a client from a template. DSPs cannot create documents."""
    from services.audit import AuditService
    
    # HIPAA: Verify user has access to this client
    _check_client_access(db, current_user, client_id)
    
    # Verify client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify template exists
    template = db.query(DocumentTemplate).filter(DocumentTemplate.id == data.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Document template not found")

    # Create document
    new_doc = ClientDocument(
        client_id=client_id,
        template_id=data.template_id,
        values=data.values,
        revision_notes=data.revision_notes,
        created_by=current_user.id
    )
    
    # Supersede previous active documents for the same template
    # We identify "same template" by having the same name and category_id
    existing_active_docs = db.query(ClientDocument, DocumentTemplate).join(
        DocumentTemplate, 
        ClientDocument.template_id == DocumentTemplate.id
    ).filter(
        ClientDocument.client_id == client_id,
        ClientDocument.is_current == True,
        DocumentTemplate.name == template.name,
        DocumentTemplate.category_id == template.category_id
    ).all()
    
    db.add(new_doc)
    db.commit() # Commit first to get new_doc.id
    db.refresh(new_doc)

    if not existing_active_docs:
        # Initial creation - no prior version, so no changes made
        audit_entry = ClientDocumentAuditLog(
            document_id=new_doc.id,
            resulting_document_id=None,  # This IS the original, no "result"
            performed_by=current_user.id,
            changes_made=False,  # No prior version to compare to
            action_type='creation',
            notes="Initial document creation"
        )
        db.add(audit_entry)

    for old_doc, old_template in existing_active_docs:
        old_doc.is_current = False
        
        # Determine action type: 'new_template' or 'edit'
        action_type = 'edit'
        if old_template.version != template.version:
            action_type = 'new_template'
            
        # Log the update
        audit_entry = ClientDocumentAuditLog(
            document_id=old_doc.id,
            resulting_document_id=new_doc.id,
            performed_by=current_user.id,
            changes_made=True,
            action_type=action_type,
            notes=f"Document updated via {action_type}"
        )
        db.add(audit_entry)
    
    # Log to main audit_logs table as well
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("create", "client_documents", new_doc.id, new_values={"client_id": client_id, "template_id": data.template_id})
        
    db.commit()

    # Return formatted response
    return ClientDocumentResponse(
        id=new_doc.id,
        client_id=new_doc.client_id,
        template_id=template.id,
        template_name=template.name,
        template_icon=template.icon,
        template_version=template.version,
        subcategory_id=template.subcategory_id,
        subcategory_name=None,
        revision_interval_days=template.revision_interval_days or 365,
        created_at=new_doc.created_at.isoformat(),
        created_by_name=f"{current_user.first_name} {current_user.last_name}",
        last_reviewed_at=None,
        last_reviewed_by_name=None,
        last_review_changes_made=None,
        review_count=0,
        form_schema=template.form_schema,
        values=new_doc.values,
        is_current=new_doc.is_current
    )


@router.post("/{client_id}/documents/{document_id}/review", status_code=status.HTTP_201_CREATED)
def review_client_document(
    client_id: int,
    document_id: int,
    request: Request,
    notes: str = None,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Mark a document as reviewed (renewed) without changing data.
    Type defaults to 'review'. DSPs cannot review documents.
    """
    from services.audit import AuditService
    
    # RBAC: DSPs cannot review documents
    if current_user.role_id == ROLE_DSP:
        raise HTTPException(status_code=403, detail="Direct care staff cannot review documents")

    # Verify client exists and check access
    get_or_404(db, Client, client_id, detail="Client not found")
    _check_client_access(db, current_user, client_id)
    
    # Verify document exists and belongs to client
    doc = db.query(ClientDocument).filter(
        ClientDocument.id == document_id,
        ClientDocument.client_id == client_id
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    if not doc.is_current:
        raise HTTPException(status_code=400, detail="Cannot review an archived document")
        
    # Create audit entry (document-specific audit log)
    audit_entry = ClientDocumentAuditLog(
        document_id=doc.id,
        resulting_document_id=None, # No new version
        performed_by=current_user.id,
        changes_made=False,
        action_type='review',
        notes=notes or "Annual review - no changes needed"
    )
    
    db.add(audit_entry)
    
    # Also log to main audit_logs for HIPAA compliance
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("update", "client_documents", document_id, new_values={"client_id": client_id, "action": "review"})
    
    db.commit()
    
    return {"message": "Document reviewed successfully"}


@router.get("/{client_id}/documents", response_model=list[ClientDocumentResponse])
def get_client_documents(
    client_id: int,
    request: Request,
    category_id: Optional[int] = None,
    include_history: bool = False,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get documents for a client. By default returns only current versions."""
    from sqlalchemy import func, or_
    from services.audit import AuditService
    
    # HIPAA Scoping: Verify user has access to this client
    _check_client_access(db, current_user, client_id)

    # Verify client exists
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Main query to get documents
    query = db.query(
        ClientDocument,
        DocumentTemplate
    ).join(
        DocumentTemplate,
        ClientDocument.template_id == DocumentTemplate.id
    ).filter(
        ClientDocument.client_id == client_id
    )

    if not include_history:
        query = query.filter(ClientDocument.is_current == True)
        
    query = query.order_by(ClientDocument.created_at.desc())
    
    if category_id:
        query = query.filter(DocumentTemplate.category_id == category_id)
    
    results = query.all()
    
    documents = []
    for doc, template in results:
        # Get creator name
        creator = db.query(Staff).filter(Staff.id == doc.created_by).first()
        created_by_name = f"{creator.first_name} {creator.last_name}" if creator else None
        
        # Get last action info - check actions ON this document OR actions that CREATED this document
        last_action = db.query(ClientDocumentAuditLog).filter(
            or_(
                ClientDocumentAuditLog.document_id == doc.id,
                ClientDocumentAuditLog.resulting_document_id == doc.id
            )
        ).order_by(ClientDocumentAuditLog.performed_at.desc()).first()
        
        last_reviewed_at = None
        last_reviewed_by_name = None
        last_review_changes_made = None
        if last_action:
            last_reviewed_at = last_action.performed_at.isoformat() if last_action.performed_at else None
            reviewer = db.query(Staff).filter(Staff.id == last_action.performed_by).first()
            last_reviewed_by_name = f"{reviewer.first_name} {reviewer.last_name}" if reviewer else None
            last_review_changes_made = last_action.changes_made
        
        # Get action count - count actions ON this document OR that CREATED this document
        review_count = db.query(ClientDocumentAuditLog).filter(
            or_(
                ClientDocumentAuditLog.document_id == doc.id,
                ClientDocumentAuditLog.resulting_document_id == doc.id
            )
        ).count()
        
        # Get subcategory name if exists
        subcategory_name = None
        if template.subcategory_id:
            subcategory = db.query(DocumentSubcategory).filter(DocumentSubcategory.id == template.subcategory_id).first()
            if subcategory:
                subcategory_name = subcategory.name
        
        documents.append(ClientDocumentResponse(
            id=doc.id,
            client_id=doc.client_id,
            template_id=doc.template_id,
            template_name=template.name,
            template_icon=template.icon,
            template_version=template.version, # Added version mapping
            subcategory_id=template.subcategory_id,
            subcategory_name=subcategory_name,
            revision_interval_days=template.revision_interval_days or 365,
            created_at=doc.created_at.isoformat() if doc.created_at else None,
            created_by_name=created_by_name,
            last_reviewed_at=last_reviewed_at,
            last_reviewed_by_name=last_reviewed_by_name,
            last_review_changes_made=last_review_changes_made,
            review_count=review_count,
            form_schema=template.form_schema,
            values=doc.values,
            is_current=doc.is_current
        ))
    
    # Log PHI access to main audit table
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_documents", None, new_values={"client_id": client_id, "document_ids": [d.id for d in documents]})
    db.commit()
    
    return documents





@router.get("/{client_id}/documents/category/{category_id}", response_model=list[ClientDocumentResponse])
def get_client_documents_by_category(
    client_id: int,
    category_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all documents for a client in a specific category."""
    # Note: get_client_documents already handles audit logging
    return get_client_documents(client_id, request, category_id, False, db, current_user)

# =============================================
# BEHAVIOR TRACKING
# =============================================

@router.get("/{client_id}/behaviors", response_model=list[BehaviorTrackingRecordWithDetails])
def get_client_behaviors(
    client_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get behavior tracking records for a specific client.
    """
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id)
    _check_client_access(db, current_user, client_id)

    # Fetch records
    records = db.query(BehaviorTrackingRecord)\
        .filter(BehaviorTrackingRecord.client_id == client_id)\
        .order_by(BehaviorTrackingRecord.recorded_at.desc())\
        .all()
    
    # Log PHI access (behavior records are sensitive PHI)
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "behavior_tracking_records", None, new_values={"client_id": client_id, "record_ids": [r.id for r in records]})
    db.commit()
        
    return records


# =============================================
# BEHAVIOR CONFIGURATION MANAGEMENT
# =============================================


@router.get("/{client_id}/behavior-configs", response_model=list[ConfigVersionOut])
def get_client_behavior_configs(
    client_id: int,
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get behavior config versions for a client."""
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id)
    _check_client_access(db, current_user, client_id)

    query = db.query(ClientBehaviorConfigVersion).filter(ClientBehaviorConfigVersion.client_id == client_id)
    if active_only:
        query = query.filter(ClientBehaviorConfigVersion.is_active == True)
    configs = query.order_by(ClientBehaviorConfigVersion.version.desc()).all()
    
    # Log PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_behavior_configs", None, new_values={"client_id": client_id, "config_ids": [c.id for c in configs]})
    db.commit()
    
    return configs


@router.post("/{client_id}/behavior-configs", response_model=ConfigVersionOut, status_code=status.HTTP_201_CREATED)
def create_client_behavior_config(
    client_id: int,
    config_in: ConfigVersionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """
    Create a new behavior config version for a client.
    Deactivates any existing active version and creates a new one with the specified behaviors.
    """
    from services.audit import AuditService
    
    client = get_or_404(db, Client, client_id)

    # Get current max version for this client
    max_version = db.query(ClientBehaviorConfigVersion.version).filter(
        ClientBehaviorConfigVersion.client_id == client_id
    ).order_by(ClientBehaviorConfigVersion.version.desc()).first()
    new_version_num = (max_version[0] + 1) if max_version else 1
    
    # Deactivate existing active config
    existing_active = db.query(ClientBehaviorConfigVersion).filter(
        ClientBehaviorConfigVersion.client_id == client_id,
        ClientBehaviorConfigVersion.is_active == True
    ).first()
    
    if existing_active:
        existing_active.is_active = False
        db.add(existing_active)
    
    # Create new config version
    new_config = ClientBehaviorConfigVersion(
        client_id=client_id,
        version=new_version_num,
        is_active=True,
        created_by=current_user.id,
        notes=config_in.notes
    )
    db.add(new_config)
    db.flush()  # Get the ID
    
    # Add behavior items
    for behavior_type_id in config_in.behavior_type_ids:
        item = ClientBehaviorConfigItem(
            config_version_id=new_config.id,
            behavior_type_id=behavior_type_id
        )
        db.add(item)
    
    # Log PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("create", "client_behavior_configs", new_config.id, new_values={"client_id": client_id, "version": new_version_num})
    
    db.commit()
    db.refresh(new_config)
    return new_config


@router.delete("/{client_id}/behavior-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_behavior_config(
    client_id: int,
    config_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Soft-delete (deactivate) a behavior config version."""
    from services.audit import AuditService
    
    config = db.query(ClientBehaviorConfigVersion).filter(
        ClientBehaviorConfigVersion.id == config_id,
        ClientBehaviorConfigVersion.client_id == client_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config.is_active = False
    
    # Log PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("delete", "client_behavior_configs", config_id, old_values={"is_active": True}, new_values={"is_active": False, "client_id": client_id})
    
    db.commit()
    return None
