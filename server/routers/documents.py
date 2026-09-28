from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional

from authentication import get_current_active_user
from authorization import (
    require_roles,
    ROLE_ADMIN,
    ROLE_DIRECTOR,
    ROLE_SITE_DIRECTOR,
    ROLE_DSP,
)
from database import get_db
from models import (
    Staff, DocumentCategory, DocumentSubcategory, DocumentTemplate, 
    ClientDocument, ClientDocumentAuditLog, ClientProgramEnrollment, Client,
    ShiftAssignment, ShiftPosition, ShiftPositionClient, Shift
)
from schemas import (
    DocumentCategoryCreate, DocumentCategoryOut,
    DocumentTemplateCreate, DocumentTemplateUpdate, DocumentTemplateOut
)
from utils import get_or_404

# Inline schemas for responses that were previously in clients.py
from pydantic import BaseModel

class SubcategoryResponse(BaseModel):
    id: int
    name: str
    icon: Optional[str]
    
    class Config:
        from_attributes = True

class CategoryWithSubcategoriesResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: Optional[str]
    subcategories: list[SubcategoryResponse]
    
    class Config:
        from_attributes = True

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
    dependencies=[Depends(get_current_active_user)]
)

# =============================================
# DOCUMENT TEMPLATES
# =============================================

@router.get("/templates", response_model=list[DocumentTemplateOut])
def get_document_templates(
    is_archived: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    """Get document templates, filtering by archived status (default: False = show active only)"""
    query = db.query(DocumentTemplate, Staff).outerjoin(
        Staff, DocumentTemplate.created_by == Staff.id
    )
    if is_archived is not None:
        query = query.filter(DocumentTemplate.is_archived == is_archived)
    
    results = query.all()
    
    return [
        DocumentTemplateOut(
            id=template.id,
            name=template.name,
            description=template.description,
            category_id=template.category_id,
            subcategory_id=template.subcategory_id,
            icon=template.icon,
            version=template.version,
            revision_interval_days=template.revision_interval_days,
            form_schema=template.form_schema,
            is_archived=template.is_archived,
            created_by=template.created_by,
            created_by_name=f"{staff.first_name} {staff.last_name}" if staff else None,
            created_at=template.created_at
        )
        for template, staff in results
    ]


@router.post("/templates", response_model=DocumentTemplateOut, status_code=status.HTTP_201_CREATED)
def create_document_template(
    data: DocumentTemplateCreate, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Create a new document template. Requires admin or director role."""
    try:
        # Explicitly convert to dict and remove created_by to avoid multiple values error
        template_data = data.model_dump()
        if "created_by" in template_data:
            del template_data["created_by"]
            
        new_template = DocumentTemplate(**template_data, created_by=current_user.id)
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        return new_template
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")


@router.put("/templates/{template_id}", response_model=DocumentTemplateOut)
def update_document_template(
    template_id: int, 
    data: DocumentTemplateUpdate, 
    db: Session = Depends(get_db), 
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """
    Create a new version of the document template.
    Marks the old one as archived and creates a new one with incremented version.
    """
    old_template = get_or_404(db, DocumentTemplate, template_id, detail="Template not found")
    
    # 1. Determine new version
    # Find all templates with same Name and Category to find max version
    # (Simplified: just increment current one, assuming we are editing the latest)
    new_version = old_template.version + 1
    
    # 2. Archive old template
    old_template.is_archived = True
    
    # 3. Create new template with updated or existing data
    # Merge old data with new data
    new_data = old_template.__dict__.copy()
    
    # Remove SQLAlchemy internal state and ID
    new_data.pop('_sa_instance_state', None)
    new_data.pop('id', None)
    new_data.pop('created_at', None)
    
    # Update with request data
    update_data = data.model_dump(exclude_unset=True)
    new_data.update(update_data)
    
    # Set system fields
    new_data['version'] = new_version
    new_data['is_archived'] = False
    new_data['created_by'] = current_user.id
    
    new_template = DocumentTemplate(**new_data)
    db.add(new_template)
    
    try:
        db.commit()
        db.refresh(new_template)
        return new_template
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="An error occurred updating the template")


@router.delete("/templates/{template_id}")
def delete_document_template(
    template_id: int, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """
    Archive a document template:
    1. Set template.is_archived = True
    2. Set all associated ClientDocuments.is_current = False
    3. Log audit entries for each affected document
    """
    template = get_or_404(db, DocumentTemplate, template_id, detail="Template not found")
    
    # 1. Archive template
    template.is_archived = True
    
    # 2. Get all documents using this template that are currently active
    affected_docs = db.query(ClientDocument).filter(
        ClientDocument.template_id == template_id,
        ClientDocument.is_current == True
    ).all()
    
    # 3. Inactivate documents and create audit entries
    for doc in affected_docs:
        doc.is_current = False
        
        # Create audit entry for each archived document
        audit_entry = ClientDocumentAuditLog(
            document_id=doc.id,
            resulting_document_id=None,  # No new version created
            performed_by=current_user.id,
            changes_made=False,  # The document content didn't change
            action_type='archived',
            notes=f"Document inactivated due to template archival (template ID: {template_id})"
        )
        db.add(audit_entry)

    db.commit()
    return {"message": f"Template {template_id} archived and {len(affected_docs)} associated documents inactivated"}


# =============================================
# DOCUMENT CATEGORIES
# =============================================

@router.get("/categories", response_model=list[CategoryWithSubcategoriesResponse])
def get_document_categories(
    include_subcategories: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get all document categories.
    If include_subcategories is True, returns nested subcategories (for mobile app).
    If False, returns categories (subcategories list will be empty or ignored by strict clients, 
    but Pydantic model includes it so it will be []).
    """
    categories = db.query(DocumentCategory).filter(DocumentCategory.is_active == True).all()
    
    result = []
    for cat in categories:
        subcategories_data = []
        if include_subcategories:
            subcategories = db.query(DocumentSubcategory).filter(
                DocumentSubcategory.category_id == cat.id,
                DocumentSubcategory.is_active == True
            ).order_by(DocumentSubcategory.name).all()
            
            subcategories_data = [
                SubcategoryResponse(
                    id=sub.id,
                    name=sub.name,
                    icon=sub.icon
                ) for sub in subcategories
            ]
        
        result.append(CategoryWithSubcategoriesResponse(
            id=cat.id,
            name=cat.name,
            description=cat.description,
            icon=cat.icon,
            subcategories=subcategories_data
        ))
    
    return result


@router.post("/categories", response_model=DocumentCategoryOut, status_code=status.HTTP_201_CREATED)
def create_document_category(
    data: DocumentCategoryCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Create a new document category (admin/director only)"""
    if current_user.role_id not in [ROLE_ADMIN, ROLE_DIRECTOR]:
        raise HTTPException(status_code=403, detail="Only admins and directors can create categories")
    
    category = DocumentCategory(**data.model_dump())
    db.add(category)
    try:
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Category with this name already exists")


# =============================================
# DOCUMENT SUBCATEGORIES
# =============================================

@router.get("/subcategories")
def get_document_subcategories(
    category_id: int = None,
    db: Session = Depends(get_db)
):
    """Get document subcategories, optionally filtered by category"""
    query = db.query(DocumentSubcategory).filter(DocumentSubcategory.is_active == True)
    if category_id:
        query = query.filter(DocumentSubcategory.category_id == category_id)
    return query.order_by(DocumentSubcategory.name).all()


@router.post("/subcategories", status_code=status.HTTP_201_CREATED)
def create_document_subcategory(
    category_id: int,
    name: str,
    icon: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """Create a new document subcategory (admin/director only)"""
    if current_user.role_id not in [ROLE_ADMIN, ROLE_DIRECTOR]:
        raise HTTPException(status_code=403, detail="Only admins and directors can create subcategories")
    
    # Verify category exists
    category = db.query(DocumentCategory).filter(DocumentCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    subcategory = DocumentSubcategory(category_id=category_id, name=name, icon=icon)
    db.add(subcategory)
    try:
        db.commit()
        db.refresh(subcategory)
        return {"id": subcategory.id, "name": subcategory.name, "category_id": subcategory.category_id}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Subcategory already exists")


# =============================================
# EXPIRED DOCUMENTS
# =============================================

@router.get("/expired/count")
def get_expired_documents_count(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get count of expired documents (latest version not reviewed within interval)."""
    from sqlalchemy import func, text
    
    # 1. Scope query based on role
    client_filter = []
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # Site Directors only see clients at their location
        valid_client_ids = db.query(ClientProgramEnrollment.client_id).filter(
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).distinct()
        client_filter.append(ClientDocument.client_id.in_(valid_client_ids))
    elif current_user.role_id == ROLE_DSP:
        # DSP only sees clients assigned to them via CURRENT shifts (today)
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
        client_filter.append(ClientDocument.client_id.in_(assigned_client_ids))

    # 2. Subquery: Latest action date per document
    # Must check both document_id AND resulting_document_id (for documents created via edit)
    from sqlalchemy import or_, union_all
    
    # Get actions where this document was the subject
    direct_actions = db.query(
        ClientDocumentAuditLog.document_id.label('doc_id'),
        ClientDocumentAuditLog.performed_at.label('action_date')
    ).filter(ClientDocumentAuditLog.document_id.isnot(None))
    
    # Get actions where this document was created as result
    result_actions = db.query(
        ClientDocumentAuditLog.resulting_document_id.label('doc_id'),
        ClientDocumentAuditLog.performed_at.label('action_date')
    ).filter(ClientDocumentAuditLog.resulting_document_id.isnot(None))
    
    all_actions = union_all(direct_actions, result_actions).subquery()
    
    latest_action_sub = db.query(
        all_actions.c.doc_id,
        func.max(all_actions.c.action_date).label('last_review_date')
    ).group_by(all_actions.c.doc_id).subquery()

    # 3. Main Query - only look at current documents
    query = db.query(func.count(ClientDocument.id)).join(
        DocumentTemplate,
        ClientDocument.template_id == DocumentTemplate.id
    ).outerjoin(
        latest_action_sub,
        ClientDocument.id == latest_action_sub.c.doc_id
    ).filter(
        ClientDocument.is_current == True,  # Only current documents
        DocumentTemplate.is_archived == False,
        *client_filter
    )

    # 5. Expiry Logic
    effective_date = func.coalesce(latest_action_sub.c.last_review_date, ClientDocument.created_at)
    
    cutoff_date = func.now() - (
        DocumentTemplate.revision_interval_days * text("INTERVAL '1 day'")
    )
    
    query = query.filter(effective_date < cutoff_date)
    
    count = query.scalar()
    
    # Log PHI access (accessing expired document counts involves client data)
    from services.audit import AuditService
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "client_documents", None, new_values={"filter": "expired_count", "count": count})
    db.commit()
    
    return {"count": count}


@router.get("/expired")
def get_expired_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get list of expired documents with details."""
    from sqlalchemy import func, text
    
    # 1. Scope query based on role
    client_filter = []
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        valid_client_ids = db.query(ClientProgramEnrollment.client_id).filter(
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).distinct()
        client_filter.append(ClientDocument.client_id.in_(valid_client_ids))
    elif current_user.role_id == ROLE_DSP:
        # DSP only sees clients assigned to them via CURRENT shifts (today)
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
        client_filter.append(ClientDocument.client_id.in_(assigned_client_ids))

    # 2. Subquery: Latest REVIEW date per document (exclude 'creation' actions)
    # Must check both document_id AND resulting_document_id (for documents created via edit)
    from sqlalchemy import or_, union_all
    
    # Get review/edit actions where this document was the subject
    direct_actions = db.query(
        ClientDocumentAuditLog.document_id.label('doc_id'),
        ClientDocumentAuditLog.performed_at.label('action_date')
    ).filter(
        ClientDocumentAuditLog.document_id.isnot(None),
        ClientDocumentAuditLog.action_type.in_(['review', 'edit'])  # Only reviews and edits
    )
    
    # Get actions where this document was created as result of an edit
    result_actions = db.query(
        ClientDocumentAuditLog.resulting_document_id.label('doc_id'),
        ClientDocumentAuditLog.performed_at.label('action_date')
    ).filter(
        ClientDocumentAuditLog.resulting_document_id.isnot(None),
        ClientDocumentAuditLog.action_type == 'edit'  # Only edits that resulted in new version
    )
    
    all_review_actions = union_all(direct_actions, result_actions).subquery()
    
    latest_review_sub = db.query(
        all_review_actions.c.doc_id,
        func.max(all_review_actions.c.action_date).label('last_review_date')
    ).group_by(all_review_actions.c.doc_id).subquery()

    # 3. Main Query with Client Join - only current documents
    query = db.query(
        Client.id.label('client_id'),
        Client.first_name,
        Client.last_name,
        ClientDocument.id.label('document_id'),
        DocumentTemplate.name.label('template_name'),
        DocumentTemplate.revision_interval_days,
        latest_review_sub.c.last_review_date,
        ClientDocument.created_at
    ).join(
        DocumentTemplate,
        ClientDocument.template_id == DocumentTemplate.id
    ).join(
        Client,
        ClientDocument.client_id == Client.id
    ).outerjoin(
        latest_review_sub,
        ClientDocument.id == latest_review_sub.c.doc_id
    ).filter(
        ClientDocument.is_current == True,  # Only current documents
        DocumentTemplate.is_archived == False,
        *client_filter
    )

    # 4. Expiry Logic - use last_review_date if available, otherwise created_at
    cutoff_date = func.now() - (
        DocumentTemplate.revision_interval_days * text("INTERVAL '1 day'")
    )
    effective_date_expr = func.coalesce(latest_review_sub.c.last_review_date, ClientDocument.created_at)
    
    query = query.filter(effective_date_expr < cutoff_date)
    
    results = query.all()
    
    # Log PHI access (accessing expired documents with client names is PHI)
    # Include list of client IDs to properly identify whose records were accessed
    unique_client_ids = list(set(r.client_id for r in results))
    
    from services.audit import AuditService
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "client_documents", None, new_values={
        "filter": "expired", 
        "count": len(results),
        "client_ids": unique_client_ids
    })
    db.commit()
    
    # Calculate due date for each result
    from datetime import timedelta
    
    return [
        {
            "client_id": r.client_id,
            "client_name": f"{r.first_name} {r.last_name}",
            "document_id": r.document_id,
            "template_name": r.template_name,
            "last_review_date": r.last_review_date.isoformat() if r.last_review_date else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "due_date": (
                (r.last_review_date if r.last_review_date else r.created_at) + timedelta(days=r.revision_interval_days)
            ).isoformat() if r.created_at else None
        }
        for r in results
    ]
