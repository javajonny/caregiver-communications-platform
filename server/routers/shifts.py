import os
from zoneinfo import ZoneInfo
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, time
from sqlalchemy import desc, func, or_, and_

from authentication import get_current_active_user
from authorization import require_roles, ROLE_ADMIN, ROLE_DIRECTOR, ROLE_SITE_DIRECTOR, ROLE_DSP
from database import get_db
from models import (
    TaskCategory, Task, TaskStatusType, ShiftTemplate, ShiftPosition,
    ShiftPositionTask, Shift, ShiftAssignment, ShiftTaskStatus, ShiftTaskStatusHistory,
    ShiftDailyLog, LogCategory, StaffLogReadStatus,
    ShiftPositionClient, Client, ClientProgramEnrollment,
    ClientBehaviorConfigVersion, ClientBehaviorConfigItem, BehaviorType, BehaviorTrackingRecord, Staff, ProgramLocation,
    ShiftEndStatusType
)
from schemas import (
    TaskCategoryCreate, TaskCategoryUpdate, TaskCategoryOut,
    TaskCreate, TaskUpdate, TaskOut,
    TaskStatusTypeCreate, TaskStatusTypeUpdate, TaskStatusTypeOut,
    ShiftTemplateCreate, ShiftTemplateUpdate, ShiftTemplateOut,
    ShiftPositionCreate, ShiftPositionUpdate, ShiftPositionOut,
    ShiftPositionTaskCreate, ShiftPositionTaskUpdate, ShiftPositionTaskOut,
    ShiftCreate, ShiftUpdate, ShiftOut, ShiftCreateFromTemplate,
    ShiftAssignmentCreate, ShiftAssignmentUpdate, ShiftAssignmentOut,
    ShiftTaskStatusCreate, ShiftTaskStatusUpdate, ShiftTaskStatusOut,
    ShiftTaskStatusHistoryCreate, ShiftTaskStatusHistoryOut,
    ShiftDailyLogCreate, ShiftDailyLogUpdate, ShiftDailyLogOut,
    LogCategoryCreate, LogCategoryUpdate, LogCategoryOut,
    UnreadShiftOut, MarkLogReadRequest,
    EndShiftRequest, EndShiftResponse, EndShiftTaskSummary,
    StaffOut
)
from utils import get_or_404, get_now

router = APIRouter(
    prefix="/shifts",
    tags=["Shifts & Tasks"],
    dependencies=[Depends(get_current_active_user)]
)


# =============================================
# TASK STATUS TYPES
# =============================================
@router.get("/task-status-types", response_model=list[TaskStatusTypeOut])
def get_task_status_types(db: Session = Depends(get_db)):
    """Get all task status types"""
    return db.query(TaskStatusType).all()


@router.get("/dashboard-stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get dashboard statistics for past shifts.
    Returns task status counts and shift end status counts.
    """
    tz = ZoneInfo(os.environ.get("TZ", "America/New_York"))
    now = get_now(tz)
    today = now.date()
    current_time = now.time()
    
    # Expire stale pending assignments before calculating stats
    # - Admin/Director: Global check (all locations)
    # - Site Director: Location-scoped check
    # - DSP: No expiration check (they can't "manage" shifts)
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        _expire_stale_assignments(db, location_id=current_user.assigned_location_id)
    elif current_user.role_id in [ROLE_ADMIN, ROLE_DIRECTOR]:
        _expire_stale_assignments(db)
    
    # Get past shifts (shifts that have ended)
    past_shifts = db.query(Shift).filter(
        (Shift.end_date < today) | 
        ((Shift.end_date == today) & (Shift.end_time < current_time))
    ).all()
    past_shift_ids = [s.id for s in past_shifts]
    
    # Get current shifts (started but not ended yet - excludes future shifts)
    # A shift is "current" if: start_date/time <= now AND end_date/time >= now
    current_shifts = db.query(Shift).filter(
        # Has started: start_date < today OR (start_date == today AND start_time <= current_time)
        ((Shift.start_date < today) | 
         ((Shift.start_date == today) & (Shift.start_time <= current_time))),
        # Hasn't ended: end_date > today OR (end_date == today AND end_time >= current_time)
        ((Shift.end_date > today) | 
         ((Shift.end_date == today) & (Shift.end_time >= current_time)))
    ).all()
    current_shift_ids = [s.id for s in current_shifts]
    
    # Task status counts for CURRENT shifts
    current_task_status_counts = {}
    if current_shift_ids:
        task_statuses = db.query(
            TaskStatusType.name,
            func.count(ShiftTaskStatus.id)
        ).join(
            ShiftTaskStatus, ShiftTaskStatus.status_id == TaskStatusType.id
        ).filter(
            ShiftTaskStatus.shift_id.in_(current_shift_ids)
        ).group_by(TaskStatusType.name).all()
        
        for name, count in task_statuses:
            current_task_status_counts[name] = count
    
    # Task status counts for PAST shifts
    past_task_status_counts = {}
    if past_shift_ids:
        task_statuses = db.query(
            TaskStatusType.name,
            func.count(ShiftTaskStatus.id)
        ).join(
            ShiftTaskStatus, ShiftTaskStatus.status_id == TaskStatusType.id
        ).filter(
            ShiftTaskStatus.shift_id.in_(past_shift_ids)
        ).group_by(TaskStatusType.name).all()
        
        for name, count in task_statuses:
            past_task_status_counts[name] = count
    
    # Past shift end status counts
    past_shift_status_counts = {}
    if past_shift_ids:
        shift_statuses = db.query(
            ShiftEndStatusType.name,
            func.count(ShiftAssignment.id)
        ).join(
            ShiftAssignment, ShiftAssignment.end_status_id == ShiftEndStatusType.id
        ).filter(
            ShiftAssignment.shift_id.in_(past_shift_ids)
        ).group_by(ShiftEndStatusType.name).all()
        
        for name, count in shift_statuses:
            past_shift_status_counts[name] = count
        
        # Count assignments still pending (not submitted)
        pending_count = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id.in_(past_shift_ids),
            ShiftAssignment.end_status_id == 4  # pending
        ).count()
        if pending_count > 0:
            past_shift_status_counts["Pending"] = pending_count
    
    # Current shift assignment status counts
    current_shift_status_counts = {}
    if current_shift_ids:
        # Completed assignments in current shifts
        completed = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id.in_(current_shift_ids),
            ShiftAssignment.end_status_id == 1  # completed
        ).count()
        if completed > 0:
            current_shift_status_counts["Completed"] = completed
        
        # Active (in progress - pending status)
        active = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id.in_(current_shift_ids),
            ShiftAssignment.end_status_id == 4  # pending
        ).count()
        if active > 0:
            current_shift_status_counts["Active"] = active
    
    return {
        "current_task_status_counts": current_task_status_counts,
        "past_task_status_counts": past_task_status_counts,
        "past_shift_status_counts": past_shift_status_counts,
        "current_shift_status_counts": current_shift_status_counts,
    }


# =============================================
# TASK CATEGORIES
# =============================================

@router.get("/task-categories", response_model=list[TaskCategoryOut])
def get_task_categories(db: Session = Depends(get_db)):
    """Get all task categories"""
    return db.query(TaskCategory).all()

@router.get("/task-categories/{category_id}", response_model=TaskCategoryOut)
def get_task_category(category_id: int, db: Session = Depends(get_db)):
    """Get a specific task category"""
    return get_or_404(db, TaskCategory, category_id, detail="Category not found")

@router.post("/task-categories", response_model=TaskCategoryOut, status_code=status.HTTP_201_CREATED)
def create_task_category(
    data: TaskCategoryCreate, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new task category"""
    new_category = TaskCategory(**data.model_dump())

    try: 
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        return new_category
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/task-categories/{category_id}", response_model=TaskCategoryOut)
def update_task_category(
    category_id: int, 
    data: TaskCategoryUpdate, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Update a task category"""
    category = get_or_404(db, TaskCategory, category_id, detail="Category not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    
    try: 
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/task-categories/{category_id}")
def deactivate_task_category(
    category_id: int, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Deactivate a task category (soft-delete). Admin/Director only for HIPAA compliance."""
    category = get_or_404(db, TaskCategory, category_id, detail="Category not found")
    
    if not category.is_active:
        raise HTTPException(status_code=400, detail="Category is already inactive")
    
    category.is_active = False
    db.commit()
    return {"message": f"Category {category_id} deactivated"}


# =============================================
# TASKS
# =============================================

@router.get("/tasks", response_model=list[TaskOut])
def get_all_tasks(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get tasks scoped by role:
    - Admin/Director: All tasks
    - Site Director: Global tasks + tasks for clients at their location
    - DSP: Global tasks + tasks for clients assigned via current shifts
    """
    from services.audit import AuditService
    from datetime import date
    
    query = db.query(Task)
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # Filter: Global tasks OR Client tasks where client is enrolled in user's location
        query = query.outerjoin(Client, Task.client_id == Client.id).outerjoin(
            ClientProgramEnrollment, 
            (Client.id == ClientProgramEnrollment.client_id) & 
            (ClientProgramEnrollment.end_date.is_(None))
        ).filter(
            (Task.client_id.is_(None)) | 
            (ClientProgramEnrollment.program_location_id == current_user.assigned_location_id)
        ).distinct()
    elif current_user.role_id == ROLE_DSP:
        # DSP: Global tasks OR tasks for clients assigned via current shifts (happening right now)
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
        now = get_now(tz)
        today = now.date()
        current_time = now.time()
        
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
                Shift.cancelled_at.is_(None),
                # Time-based filter: shift must be happening right now
                or_(
                    # Non-overnight shift
                    and_(
                        Shift.start_date == Shift.end_date,
                        Shift.start_time <= current_time,
                        Shift.end_time >= current_time
                    ),
                    # Overnight shift
                    and_(
                        Shift.end_date > Shift.start_date,
                        or_(
                            Shift.start_time <= current_time,
                            Shift.end_time >= current_time
                        )
                    )
                )
            )
            .distinct()
        )
        query = query.filter(
            (Task.client_id.is_(None)) |
            (Task.client_id.in_(assigned_client_ids))
        )
    
    tasks = query.all()
    
    # Log PHI access - extract client_ids from client-specific tasks
    client_ids = list(set(t.client_id for t in tasks if t.client_id is not None))
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "tasks", None, new_values={"task_ids": [t.id for t in tasks], "client_ids": client_ids})
    db.commit()
    
    return tasks


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get a specific task with role-based access control:
    - Admin/Director: Any task
    - Site Director: Global tasks + tasks for clients at their location
    - DSP: Global tasks + tasks for clients assigned via current shifts
    """
    from services.audit import AuditService
    from datetime import date
    
    task = get_or_404(db, Task, task_id, detail="Task not found")
    
    # Access control: check if user can access this task
    if task.client_id:
        # Client-specific task - check access
        if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
            # Site Director: check if client is at their location
            has_access = db.query(ClientProgramEnrollment).filter(
                ClientProgramEnrollment.client_id == task.client_id,
                ClientProgramEnrollment.program_location_id == current_user.assigned_location_id,
                ClientProgramEnrollment.is_active == True
            ).first()
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied: client not at your location")
        elif current_user.role_id == ROLE_DSP:
            # DSP: check if client assigned via current shifts (happening right now)
            from datetime import datetime
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
            now = datetime.now(tz)
            today = now.date()
            current_time = now.time()
            
            has_access = (
                db.query(ShiftPositionClient)
                .join(ShiftPosition, ShiftPositionClient.shift_position_id == ShiftPosition.id)
                .join(ShiftAssignment, ShiftAssignment.shift_position_id == ShiftPosition.id)
                .join(Shift, ShiftAssignment.shift_id == Shift.id)
                .filter(
                    ShiftPositionClient.client_id == task.client_id,
                    ShiftAssignment.staff_id == current_user.id,
                    ShiftAssignment.ended_at.is_(None),
                    Shift.start_date <= today,
                    Shift.end_date >= today,
                    Shift.cancelled_at.is_(None),
                    # Time-based filter: shift must be happening right now
                    or_(
                        # Non-overnight shift
                        and_(
                            Shift.start_date == Shift.end_date,
                            Shift.start_time <= current_time,
                            Shift.end_time >= current_time
                        ),
                        # Overnight shift
                        and_(
                            Shift.end_date > Shift.start_date,
                            or_(
                                Shift.start_time <= current_time,
                                Shift.end_time >= current_time
                            )
                        )
                    )
                )
                .first()
            )
            if not has_access:
                raise HTTPException(status_code=403, detail="Access denied: client not assigned to your current shifts")
    
    # Log all task access for comprehensive audit trail
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read", "tasks", task.id, new_values={"client_id": task.client_id})
    db.commit()
    
    return task


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new task"""
    from services.audit import AuditService
    
    # Site Director Scoping
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        # 1. Global Tasks (client_id is None) -> ALLOWED (User request)
        
        # 2. If client-specific, verify client is at their location
        if data.client_id:
            enrollment = db.query(ClientProgramEnrollment).filter(
                ClientProgramEnrollment.client_id == data.client_id,
                ClientProgramEnrollment.program_location_id == current_user.assigned_location_id,
                ClientProgramEnrollment.is_active == True
            ).first()
            if not enrollment:
                raise HTTPException(status_code=403, detail="You can only create tasks for clients at your assigned location")

    try:
        new_task = Task(**data.model_dump())
        db.add(new_task)
        db.flush()
        
        # Log PHI access if client-specific
        if new_task.client_id:
            audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("create", "tasks", new_task.id, new_values={"client_id": new_task.client_id, "name": new_task.name})
        
        db.commit()
        db.refresh(new_task)
        return new_task
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Task already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.post("/custom-tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_custom_task(
    data: TaskCreate, 
    request: Request,
    db: Session = Depends(get_db), 
    staff: Staff = Depends(get_current_active_user)
):
    """Caregiver creates a custom task for their current shift only (non-recurring).
    The task will appear only for this shift and won't recur because is_custom=True.
    """
    from services.audit import AuditService
    
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    now = get_now(tz)
    today = now.date()
    current_time = now.time()

    # Find staff member's current shift (the one happening right now)
    current_assignment = (
        db.query(ShiftAssignment, Shift, ShiftPosition)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .join(ShiftPosition, ShiftAssignment.shift_position_id == ShiftPosition.id)
        .filter(ShiftAssignment.staff_id == staff.id)
    )
    
    from sqlalchemy import and_, or_
    time_filter = or_(
        # Same-day shift
        and_(
            Shift.start_date == today,
            Shift.end_date == today,
            Shift.start_time <= current_time,
            Shift.end_time >= current_time
        ),
        # Overnight started yesterday, still active
        and_(
            Shift.start_date == today - timedelta(days=1),
            Shift.end_date == today,
            current_time <= Shift.end_time
        ),
        # Overnight starts today
        and_(
            Shift.start_date == today,
            Shift.end_date == today + timedelta(days=1),
            current_time >= Shift.start_time
        )
    )
    
    current_assignment = current_assignment.filter(time_filter).first()
    
    if not current_assignment:
        raise HTTPException(status_code=404, detail="No current shift found for staff")
    
    assignment, shift, position = current_assignment

    try:
        # Create task marked as custom (will not recur)
        new_task = Task(
            **data.model_dump(),
            is_custom=True,  # Mark as custom task
            created_by=staff.id  # Track who created this task
        )
        db.add(new_task)
        db.flush()

        # Create shift_task_status entry (ties to shift + position, not recurring)
        pending_status_type = db.query(TaskStatusType).filter(TaskStatusType.id == 1).first()
        if not pending_status_type:
            raise HTTPException(status_code=500, detail="Pending task status type (id=1) not found")

        new_status = ShiftTaskStatus(
            shift_id=shift.id,
            task_id=new_task.id,
            shift_position_id=position.id,  # Store position for efficient filtering
            status_id=pending_status_type.id,
            scheduled_start_time=None,
            scheduled_end_time=None,
        )
        db.add(new_status)
        
        # Log PHI access if client-specific
        if new_task.client_id:
            audit = AuditService(db=db, user_id=staff.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("create", "tasks", new_task.id, new_values={"client_id": new_task.client_id, "name": new_task.name, "is_custom": True})
        
        db.commit()
        db.refresh(new_task)
        return new_task
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Task already exists for this shift")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int, 
    data: TaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Update a task"""
    from services.audit import AuditService
    
    task = get_or_404(db, Task, task_id, detail="Task not found")
    
    # Site Director Scoping
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        # 1. Cannot edit Global Tasks
        if task.client_id is None:
            raise HTTPException(status_code=403, detail="Site Directors cannot update Global tasks")
        
        # 2. Cannot edit tasks for other locations
        enrollment = db.query(ClientProgramEnrollment).filter(
            ClientProgramEnrollment.client_id == task.client_id,
            ClientProgramEnrollment.program_location_id == current_user.assigned_location_id
        ).first()
        if not enrollment:
            raise HTTPException(status_code=403, detail="You can only update tasks for clients at your assigned location")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    
    try:
        # Log PHI access if client-specific
        if task.client_id:
            audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("update", "tasks", task.id, new_values={"client_id": task.client_id})
        
        db.commit()
        db.refresh(task)
        return task
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Task already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/tasks/{task_id}")
def deactivate_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Deactivate a task (soft-delete). Admin/Director only for HIPAA compliance."""
    from services.audit import AuditService
    
    task = get_or_404(db, Task, task_id, detail="Task not found")
    
    if not task.is_active:
        raise HTTPException(status_code=400, detail="Task is already inactive")
    
    task.is_active = False
    
    # Log PHI access if client-specific
    if task.client_id:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("delete", "tasks", task.id, new_values={"client_id": task.client_id})
    
    db.commit()
    return {"message": f"Task {task_id} deactivated"}


# =============================================
# SHIFT TEMPLATES
# =============================================

@router.get("/templates", response_model=list[ShiftTemplateOut])
def get_all_shift_templates(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get all active (non-archived) shift templates scoped by role:
    - Admin/Director: All templates
    - Site Director: Templates at their assigned location
    - DSP: Only templates for shifts happening right now
    """
    from datetime import date
    
    query = db.query(ShiftTemplate).filter(ShiftTemplate.archived_at.is_(None))  # Exclude archived
    
    # Site Directors only see templates at their assigned location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        query = query.filter(ShiftTemplate.program_location_id == current_user.assigned_location_id)
    elif current_user.role_id == ROLE_DSP:
        # DSP: only see templates for shifts happening right now
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
        now = datetime.now(tz)
        today = now.date()
        current_time = now.time()
        
        template_ids = db.query(Shift.shift_template_id).join(
            ShiftAssignment, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            ShiftAssignment.ended_at.is_(None),
            Shift.start_date <= today,
            Shift.end_date >= today,
            Shift.cancelled_at.is_(None),
            Shift.shift_template_id.isnot(None),
            # Time-based filter: shift must be happening right now
            or_(
                # Non-overnight shift: current time between start and end (start_date == end_date)
                and_(
                    Shift.start_date == Shift.end_date,
                    Shift.start_time <= current_time,
                    Shift.end_time >= current_time
                ),
                # Overnight shift: current time after start OR before end (end_date > start_date)
                and_(
                    Shift.end_date > Shift.start_date,
                    or_(
                        Shift.start_time <= current_time,
                        Shift.end_time >= current_time
                    )
                )
            )
        ).distinct().all()
        template_id_list = [tid for (tid,) in template_ids]
        
        if template_id_list:
            query = query.filter(ShiftTemplate.id.in_(template_id_list))
        else:
            return []
    
    return query.all()


@router.get("/templates/{template_id}", response_model=ShiftTemplateOut)
def get_shift_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get a specific shift template with access control:
    - Admin/Director: Any template
    - Site Director: Templates at their assigned location
    - DSP: Only templates for shifts happening right now
    """
    from datetime import date
    
    template = get_or_404(db, ShiftTemplate, template_id, detail="Template not found")
    
    # Access control
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if template.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: template not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: check if they have a current active shift using this template (happening right now)
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
        now = datetime.now(tz)
        today = now.date()
        current_time = now.time()
        
        has_access = db.query(Shift).join(
            ShiftAssignment, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            ShiftAssignment.ended_at.is_(None),
            Shift.shift_template_id == template_id,
            Shift.start_date <= today,
            Shift.end_date >= today,
            Shift.cancelled_at.is_(None),
            # Time-based filter: shift must be happening right now
            or_(
                # Non-overnight shift
                and_(
                    Shift.start_date == Shift.end_date,
                    Shift.start_time <= current_time,
                    Shift.end_time >= current_time
                ),
                # Overnight shift
                and_(
                    Shift.end_date > Shift.start_date,
                    or_(
                        Shift.start_time <= current_time,
                        Shift.end_time >= current_time
                    )
                )
            )
        ).first()
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: template not for your current shift")
    
    return template


@router.post("/templates", response_model=ShiftTemplateOut, status_code=status.HTTP_201_CREATED)
def create_shift_template(
    data: ShiftTemplateCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new shift template. Site Directors can only create at their location."""
    # Site Directors can only create templates at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != data.program_location_id:
            raise HTTPException(status_code=403, detail="You can only create templates at your assigned location")
    
    try:
        new_template = ShiftTemplate(
            **data.model_dump(),
            created_by=current_user.id  # HIPAA audit trail
        )
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        return new_template
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift template already exists")
        elif "violates check constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Data violates a table constraint")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/templates/{template_id}", response_model=ShiftTemplateOut)
def update_shift_template(
    template_id: int,
    data: ShiftTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Update a shift template. Site Directors can only update at their location."""
    template = get_or_404(db, ShiftTemplate, template_id, detail="Template not found")
    
    # Site Directors can only update templates at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != template.program_location_id:
            raise HTTPException(status_code=403, detail="You can only update templates at your assigned location")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    
    try:
        db.commit()
        db.refresh(template)
        return template
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift template already exists")
        elif "violates check constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Data violates a table constraint")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/templates/{template_id}")
def deactivate_shift_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Archive a shift template (soft-delete). Site Directors can only archive at their location.
    
    Sets archived_at timestamp and archived_by for audit trail instead of hard-deleting.
    Cannot archive templates that have active or future non-cancelled shifts.
    """
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    now = datetime.now(tz)
    today = now.date()
    current_time = now.time()
    
    template = get_or_404(db, ShiftTemplate, template_id, detail="Template not found")
    
    # Site Directors can only archive templates at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if not current_user.assigned_location_id or current_user.assigned_location_id != template.program_location_id:
            raise HTTPException(status_code=403, detail="Site Directors can only archive templates at their assigned location")
    
    if template.archived_at is not None:
        raise HTTPException(status_code=400, detail="Template is already archived")
    
    # Check if template has any active or future (non-cancelled) shifts
    # A shift is "active or future" if: end_date > today OR (end_date == today AND end_time >= current_time)
    active_future_shifts = db.query(Shift).filter(
        Shift.shift_template_id == template_id,
        Shift.cancelled_at.is_(None),  # Not cancelled
        (
            (Shift.end_date > today) | 
            ((Shift.end_date == today) & (Shift.end_time >= current_time))
        )
    ).count()
    
    if active_future_shifts > 0:
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot archive template with {active_future_shifts} active/future shift(s). Cancel or complete these shifts first."
        )
    
    template.is_active = False
    template.archived_at = datetime.now(tz)
    template.archived_by = current_user.id
    db.commit()
    return {"message": f"Template {template_id} archived"}


# =============================================
# SHIFT POSITIONS
# =============================================

@router.get("/positions", response_model=list[ShiftPositionOut])
def get_shift_positions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get shift positions scoped by role:
    - Admin/Director: All positions
    - Site Director: Positions at their assigned location
    - DSP: Own positions from shifts happening right now
    """
    from services.audit import AuditService
    from datetime import date
    
    query = db.query(ShiftPosition).filter(ShiftPosition.is_active == True)
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # Site Director: positions at their location (via template)
        query = query.join(ShiftTemplate, ShiftPosition.shift_template_id == ShiftTemplate.id).filter(
            ShiftTemplate.program_location_id == current_user.assigned_location_id
        )
    elif current_user.role_id == ROLE_DSP:
        # DSP: only their own position from current active shift assignments (happening right now)
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
        now = datetime.now(tz)
        today = now.date()
        current_time = now.time()
        
        position_ids = db.query(ShiftAssignment.shift_position_id).join(
            Shift, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            ShiftAssignment.ended_at.is_(None),
            Shift.start_date <= today,
            Shift.end_date >= today,
            Shift.cancelled_at.is_(None),
            # Time-based filter: shift must be happening right now
            or_(
                # Non-overnight shift
                and_(
                    Shift.start_date == Shift.end_date,
                    Shift.start_time <= current_time,
                    Shift.end_time >= current_time
                ),
                # Overnight shift
                and_(
                    Shift.end_date > Shift.start_date,
                    or_(
                        Shift.start_time <= current_time,
                        Shift.end_time >= current_time
                    )
                )
            )
        ).distinct().all()
        position_id_list = [pid for (pid,) in position_ids]
        
        if position_id_list:
            query = query.filter(ShiftPosition.id.in_(position_id_list))
        else:
            return []
    
    positions = query.all()
    
    # Check for positions with client assignments
    client_ids = set()
    for pos in positions:
        for pc in pos.clients:
            client_ids.add(pc.client_id)
    
    if client_ids:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read_list", "shift_positions", None, new_values={"client_ids": list(client_ids)})
        db.commit()
    
    return positions


@router.post("/positions", response_model=ShiftPositionOut, status_code=status.HTTP_201_CREATED)
def create_shift_position(
    data: ShiftPositionCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new shift position. Site Directors can only create at their location."""
    from services.audit import AuditService
    try:
        # Extract client_ids manually as they are not on the model
        client_ids = data.client_ids
        position_data = data.model_dump(exclude={'client_ids'})
        
        # Verify Shift Template exists and get its location
        template = get_or_404(db, ShiftTemplate, data.shift_template_id, detail="Shift Template not found")
        
        # Site Directors can only create positions for templates at their location
        if current_user.role_id == ROLE_SITE_DIRECTOR:
            if not current_user.assigned_location_id or current_user.assigned_location_id != template.program_location_id:
                raise HTTPException(status_code=403, detail="Site Directors can only create positions for templates at their assigned location")
        
        # Check if active position with same name already exists for this template
        existing_active_position = db.query(ShiftPosition).filter(
            ShiftPosition.shift_template_id == data.shift_template_id,
            ShiftPosition.position_name == data.position_name,
            ShiftPosition.is_active == True
        ).first()
        
        if existing_active_position:
            raise HTTPException(status_code=409, detail=f"Position '{data.position_name}' already exists for this template")
        
        # Add clients with validation
        if client_ids:
            # Verify all clients are enrolled in the template's location
            valid_clients_count = db.query(ClientProgramEnrollment).filter(
                ClientProgramEnrollment.client_id.in_(client_ids),
                ClientProgramEnrollment.program_location_id == template.program_location_id
            ).distinct(ClientProgramEnrollment.client_id).count()
            
            if valid_clients_count != len(set(client_ids)):
                 raise HTTPException(
                    status_code=400, 
                    detail="One or more clients are not enrolled in the location of this shift template."
                )

        new_position = ShiftPosition(**position_data)
        new_position.created_by = current_user.id
        db.add(new_position)
        db.flush() # flush to get the id

        if client_ids:
            for cid in client_ids:
                db.add(ShiftPositionClient(shift_position_id=new_position.id, client_id=cid))
            
            # Log PHI access - client assignment
            audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("create", "shift_positions", new_position.id, new_values={"client_ids": client_ids})
        
        db.commit()
        db.refresh(new_position)
        return new_position
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected database error occurred")


@router.put("/positions/{position_id}", response_model=ShiftPositionOut)
def update_shift_position(
    position_id: int, 
    data: ShiftPositionUpdate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Update a shift position. Site Directors can only update at their location."""
    from services.audit import AuditService
    
    position = get_or_404(db, ShiftPosition, position_id, detail="Position not found")
    
    # Site Directors can only update positions for templates at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        template = get_or_404(db, ShiftTemplate, position.shift_template_id, detail="Shift Template not found")
        if not current_user.assigned_location_id or current_user.assigned_location_id != template.program_location_id:
            raise HTTPException(status_code=403, detail="Site Directors can only update positions for templates at their assigned location")
    
    # helper for client updates
    if data.client_ids is not None:
        client_ids = data.client_ids
        if client_ids:
             # Verify all clients are enrolled in the template's location
            # Note: position.template should be loaded or we access via shift_template_id
            # We can use position.shift_template_id direct access
            template = get_or_404(db, ShiftTemplate, position.shift_template_id, detail="Shift Template not found")

            valid_clients_count = db.query(ClientProgramEnrollment).filter(
                ClientProgramEnrollment.client_id.in_(client_ids),
                ClientProgramEnrollment.program_location_id == template.program_location_id
            ).distinct(ClientProgramEnrollment.client_id).count()
            
            if valid_clients_count != len(set(client_ids)):
                 raise HTTPException(
                    status_code=400, 
                    detail="One or more clients are not enrolled in the location of this shift template."
                )

        # remove existing
        db.query(ShiftPositionClient).filter(ShiftPositionClient.shift_position_id == position_id).delete()
        # add new
        for cid in client_ids:
            db.add(ShiftPositionClient(shift_position_id=position_id, client_id=cid))
        
        # Log PHI access - client assignment update
        if client_ids:
            audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("update", "shift_positions", position_id, new_values={"client_ids": client_ids})

    for key, value in data.model_dump(exclude={'client_ids'}, exclude_unset=True).items():
        setattr(position, key, value)
    
    try:
        db.commit()
        db.refresh(position)
        return position
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift position already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/positions/{position_id}")
def delete_shift_position(
    position_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Archive a shift position (soft-delete). Site Directors can only archive at their location."""
    from services.audit import AuditService
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import os
    
    position = get_or_404(db, ShiftPosition, position_id, detail="Position not found")
    
    # Site Directors can only delete positions for templates at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        template = get_or_404(db, ShiftTemplate, position.shift_template_id, detail="Shift Template not found")
        if not current_user.assigned_location_id or current_user.assigned_location_id != template.program_location_id:
            raise HTTPException(status_code=403, detail="Site Directors can only delete positions for templates at their assigned location")
    
    if not position.is_active:
        raise HTTPException(status_code=400, detail="Position is already archived")
    
    # Log PHI access if position has client assignments
    client_ids = [pc.client_id for pc in position.clients]
    if client_ids:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("archive", "shift_positions", position_id, new_values={"client_ids": client_ids})
    
    # Soft-delete
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    position.is_active = False
    position.archived_at = datetime.now(tz)
    position.archived_by = current_user.id
    db.commit()
    return {"message": f"Position {position_id} archived"}


# =============================================
# SHIFT POSITION TASKS
# =============================================

@router.get("/position-tasks", response_model=list[ShiftPositionTaskOut])
def get_all_shift_position_tasks(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get shift position tasks scoped by role:
    - Admin/Director: All position tasks
    - Site Director: Position tasks at their assigned location
    - DSP: Tasks for their own position(s) from shifts happening right now
    """
    from services.audit import AuditService
    from datetime import date
    
    query = db.query(ShiftPositionTask).filter(ShiftPositionTask.is_active == True)
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # Site Director: position tasks at their location
        query = query.join(ShiftPosition, ShiftPositionTask.shift_position_id == ShiftPosition.id).join(
            ShiftTemplate, ShiftPosition.shift_template_id == ShiftTemplate.id
        ).filter(
            ShiftTemplate.program_location_id == current_user.assigned_location_id
        )
    elif current_user.role_id == ROLE_DSP:
        # DSP: only tasks for their own position(s) from current active shift assignments (happening right now)
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
        now = datetime.now(tz)
        today = now.date()
        current_time = now.time()
        
        position_ids = db.query(ShiftAssignment.shift_position_id).join(
            Shift, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            ShiftAssignment.ended_at.is_(None),
            Shift.start_date <= today,
            Shift.end_date >= today,
            Shift.cancelled_at.is_(None),
            # Time-based filter: shift must be happening right now
            or_(
                # Non-overnight shift
                and_(
                    Shift.start_date == Shift.end_date,
                    Shift.start_time <= current_time,
                    Shift.end_time >= current_time
                ),
                # Overnight shift
                and_(
                    Shift.end_date > Shift.start_date,
                    or_(
                        Shift.start_time <= current_time,
                        Shift.end_time >= current_time
                    )
                )
            )
        ).distinct().all()
        position_id_list = [pid for (pid,) in position_ids]
        
        if position_id_list:
            query = query.filter(ShiftPositionTask.shift_position_id.in_(position_id_list))
        else:
            return []
    
    position_tasks = query.all()
    
    # Check for client-specific tasks and log if any exist
    client_ids = set()
    for pt in position_tasks:
        task = db.query(Task).filter(Task.id == pt.task_id).first()
        if task and task.client_id:
            client_ids.add(task.client_id)
    
    if client_ids:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read_list", "shift_position_tasks", None, new_values={"client_ids": list(client_ids)})
        db.commit()
    
    return position_tasks

@router.get("/position-tasks/{position_task_id}", response_model=ShiftPositionTaskOut)
def get_shift_position_task(
    position_task_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get a specific shift position task with access control"""
    from services.audit import AuditService
    from datetime import date
    
    position_task = get_or_404(db, ShiftPositionTask, position_task_id, detail="Position task not found")
    
    # Access control for Site Directors and DSPs
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        # Check if position task is for their location
        template = db.query(ShiftTemplate).join(
            ShiftPosition, ShiftTemplate.id == ShiftPosition.shift_template_id
        ).filter(ShiftPosition.id == position_task.shift_position_id).first()
        
        if not template or template.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: position task not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: check if position task is for their position in a shift happening right now
        from datetime import date, datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
        now = datetime.now(tz)
        today = now.date()
        current_time = now.time()
        
        has_access = db.query(ShiftAssignment).join(
            Shift, ShiftAssignment.shift_id == Shift.id
        ).join(
            ShiftTemplate, Shift.shift_template_id == ShiftTemplate.id
        ).join(
            ShiftPosition, ShiftPosition.shift_template_id == ShiftTemplate.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            ShiftAssignment.ended_at.is_(None),
            ShiftPosition.id == position_task.shift_position_id,
            Shift.start_date <= today,
            Shift.end_date >= today,
            Shift.cancelled_at.is_(None),
            # Time-based filter: shift must be happening right now
            or_(
                # Non-overnight shift
                and_(
                    Shift.start_date == Shift.end_date,
                    Shift.start_time <= current_time,
                    Shift.end_time >= current_time
                ),
                # Overnight shift
                and_(
                    Shift.end_date > Shift.start_date,
                    or_(
                        Shift.start_time <= current_time,
                        Shift.end_time >= current_time
                    )
                )
            )
        ).first()
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: position task not for your current shifts")
    
    # Log if linked task is client-specific
    task = db.query(Task).filter(Task.id == position_task.task_id).first()
    if task and task.client_id:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read", "shift_position_tasks", position_task_id, new_values={"client_id": task.client_id, "task_id": task.id})
        db.commit()
    
    return position_task


@router.post("/position-tasks", response_model=ShiftPositionTaskOut, status_code=status.HTTP_201_CREATED)
def create_shift_position_task(
    data: ShiftPositionTaskCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new shift position task. Site Directors can only create at their location."""
    from services.audit import AuditService
    
    # Site Directors can only create position tasks at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        template = db.query(ShiftTemplate).join(
            ShiftPosition, ShiftTemplate.id == ShiftPosition.shift_template_id
        ).filter(ShiftPosition.id == data.shift_position_id).first()
        
        if not template or template.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Site Directors can only create position tasks at their assigned location")
    
    try:
        new_task = ShiftPositionTask(**data.model_dump(), created_by=current_user.id)
        db.add(new_task)
        db.flush()
        
        # Log if linked task is client-specific
        task = db.query(Task).filter(Task.id == new_task.task_id).first()
        if task and task.client_id:
            audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("create", "shift_position_tasks", new_task.id, new_values={"client_id": task.client_id, "task_id": task.id})
        
        db.commit()
        db.refresh(new_task)
        return new_task
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift position task already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/position-tasks/{position_task_id}", response_model=ShiftPositionTaskOut)
def update_shift_position_task(
    position_task_id: int, 
    data: ShiftPositionTaskUpdate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Update a shift position task. Site Directors can only update at their location."""
    from services.audit import AuditService
    
    position_task = get_or_404(db, ShiftPositionTask, position_task_id, detail="Position task not found")
    
    # Site Directors can only update position tasks at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        template = db.query(ShiftTemplate).join(
            ShiftPosition, ShiftTemplate.id == ShiftPosition.shift_template_id
        ).filter(ShiftPosition.id == position_task.shift_position_id).first()
        
        if not template or template.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Site Directors can only update position tasks at their assigned location")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(position_task, key, value)
    
    try:
        # Log if linked task is client-specific
        task = db.query(Task).filter(Task.id == position_task.task_id).first()
        if task and task.client_id:
            audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
            audit.log_data_access("update", "shift_position_tasks", position_task_id, new_values={"client_id": task.client_id, "task_id": task.id})
        
        db.commit()
        db.refresh(position_task)
        return position_task
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift position task already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/position-tasks/{position_task_id}")
def delete_shift_position_task(
    position_task_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Archive a shift position task (soft-delete). Site Directors can only archive at their location."""
    from services.audit import AuditService
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import os
    
    position_task = get_or_404(db, ShiftPositionTask, position_task_id, detail="Position task not found")
    
    # Site Directors can only archive position tasks at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        template = db.query(ShiftTemplate).join(
            ShiftPosition, ShiftTemplate.id == ShiftPosition.shift_template_id
        ).filter(ShiftPosition.id == position_task.shift_position_id).first()
        
        if not template or template.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Site Directors can only archive position tasks at their assigned location")
    
    if not position_task.is_active:
        raise HTTPException(status_code=400, detail="Position task is already archived")
    
    # Log if linked task is client-specific
    task = db.query(Task).filter(Task.id == position_task.task_id).first()
    if task and task.client_id:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("archive", "shift_position_tasks", position_task_id, new_values={"client_id": task.client_id, "task_id": task.id})
    
    # Soft-delete
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    position_task.is_active = False
    position_task.archived_at = datetime.now(tz)
    position_task.archived_by = current_user.id
    db.commit()
    return {"message": f"Position task {position_task_id} archived"}


# =============================================
# DAILY LOG NOTES CATEGORIES
# =============================================

@router.get("/log-categories", response_model=list[LogCategoryOut])
def get_all_log_categories(db: Session = Depends(get_db)):
    """Get all active log categories"""
    return db.query(LogCategory).filter(LogCategory.is_active == True).all()


@router.get("/log-categories/{category_id}", response_model=LogCategoryOut)
def get_log_category(category_id: int, db: Session = Depends(get_db)):
    """Get a specific log category"""
    return get_or_404(db, LogCategory, category_id, detail="Log category not found")


@router.post("/log-categories", response_model=LogCategoryOut, status_code=status.HTTP_201_CREATED)
def create_log_category(
    data: LogCategoryCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Create a new log category. Requires admin or director role."""
    try:
        new_category = LogCategory(**data.model_dump())
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        return new_category
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Log category already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.put("/log-categories/{category_id}", response_model=LogCategoryOut)
def update_log_category(
    category_id: int,
    data: LogCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Update a log category. Requires admin or director role."""
    category = get_or_404(db, LogCategory, category_id, detail="Log category not found")
    
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    
    try:
        db.commit()
        db.refresh(category)
        return category
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Log category already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/log-categories/{category_id}")
def delete_log_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director"]))
):
    """Deactivate a log category (soft-delete). Requires admin or director role."""
    category = get_or_404(db, LogCategory, category_id, detail="Log category not found")
    
    if not category.is_active:
        raise HTTPException(status_code=400, detail="Log category is already deactivated")
    
    category.is_active = False
    db.commit()
    return {"message": f"Log category {category_id} deactivated"}


# =============================================
# SHIFTS
# =============================================

GRACE_PERIOD_MINUTES_PORTAL = 10  # Same grace period as mobile app

def _expire_stale_assignments(db: Session, location_id: int = None):
    """
    Helper to mark pending assignments as timed out if their shift 
    ended more than GRACE_PERIOD minutes ago. Also marks their tasks as not_completed.
    
    Args:
        db: Database session
        location_id: If provided, only expire assignments for shifts at this location.
                    If None, expire all locations (for admins/directors).
    """
    tz = ZoneInfo(os.environ.get("TZ", "America/New_York"))
    now = datetime.now(tz)
    
    # Find all pending assignments
    query = (
        db.query(ShiftAssignment)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .filter(ShiftAssignment.end_status_id == 4)  # 'pending'
    )
    
    # Scope to location if provided
    if location_id:
        query = query.filter(Shift.program_location_id == location_id)
    
    pending_assignments = query.all()
    
    changed = False
    for assignment in pending_assignments:
        shift = db.query(Shift).filter(Shift.id == assignment.shift_id).first()
        if shift:
            shift_end_dt = datetime.combine(shift.end_date, shift.end_time)
            if shift_end_dt.tzinfo is None:
                shift_end_dt = shift_end_dt.replace(tzinfo=tz)
            
            if now > shift_end_dt + timedelta(minutes=GRACE_PERIOD_MINUTES_PORTAL):
                assignment.end_status_id = 2  # 'timeout'
                
                # Get pending tasks to update and log to history
                pending_tasks = db.query(ShiftTaskStatus).filter(
                    ShiftTaskStatus.shift_id == shift.id,
                    ShiftTaskStatus.shift_position_id == assignment.shift_position_id,
                    ShiftTaskStatus.status_id == 1  # pending
                ).all()
                
                for task_status in pending_tasks:
                    old_status_id = task_status.status_id
                    task_status.status_id = 5  # not_completed
                    
                    # Log to history for HIPAA audit trail
                    history_entry = ShiftTaskStatusHistory(
                        shift_task_status_id=task_status.id,
                        from_status_id=old_status_id,
                        to_status_id=5,
                        changed_by=None,  # System-initiated (timeout)
                        notes="Auto-marked not_completed due to shift timeout"
                    )
                    db.add(history_entry)
                
                changed = True
    
    if changed:
        db.commit()


@router.get("", response_model=list[ShiftOut])
def get_shifts(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get shifts scoped by role:
    - Admin/Director: All shifts
    - Site Director: Shifts at their assigned location
    - DSP: Shifts at locations where they have shift assignments
    """
    # Expire stale pending assignments before returning data
    # Site Directors only expire within their location scope
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        _expire_stale_assignments(db, location_id=current_user.assigned_location_id)
    else:
        _expire_stale_assignments(db)
    
    query = db.query(Shift).filter(Shift.cancelled_at.is_(None))  # Exclude cancelled
    
    # Site Directors only see shifts at their assigned location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        query = query.filter(Shift.program_location_id == current_user.assigned_location_id)
    elif current_user.role_id == ROLE_DSP:
        # DSP: Only see shifts at locations where they have shift assignments
        dsp_location_ids = db.query(Shift.program_location_id).join(
            ShiftAssignment, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            Shift.cancelled_at.is_(None)
        ).distinct().all()
        location_ids = [loc_id for (loc_id,) in dsp_location_ids]
        
        if location_ids:
            query = query.filter(Shift.program_location_id.in_(location_ids))
        else:
            # No shift assignments - return empty list
            return []
    
    return query.all()


@router.post("/from-template", response_model=list[ShiftOut], status_code=status.HTTP_201_CREATED)
def create_shifts_from_template(
    data: ShiftCreateFromTemplate, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create shifts based on a template with optional weekly repetition"""
    template = get_or_404(db, ShiftTemplate, data.shift_template_id, detail="Shift Template not found")
    
    # Site Directors can only create shifts for their assigned location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if template.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=404, detail="Shift Template not found")
    
    # Validation: Ensure start_date matches template's weekday
    # Python weekday(): Monday=0, Sunday=6 (same as our template)
    if template.start_day_of_week is not None:
        DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        selected_weekday = data.start_date.weekday()
        if selected_weekday != template.start_day_of_week:
            raise HTTPException(
                status_code=400,
                detail=f"This template is for {DAYS[template.start_day_of_week]}s only. Selected date falls on a {DAYS[selected_weekday]}."
            )
    
    created_shifts = []
    start_time = template.start_time
    end_time = template.end_time
    is_overnight = template.is_overnight
    weeks = data.repeat_weeks or 1
    
    # Validation: Ensure all positions are assigned
    template_positions = db.query(ShiftPosition).filter(ShiftPosition.shift_template_id == template.id).all()
    required_ids = {p.id for p in template_positions}
    assigned_ids = {int(k) for k in data.assignments.keys()}
    
    if not required_ids.issubset(assigned_ids):
        raise HTTPException(status_code=400, detail="All shift positions must be assigned to a staff member")

    # Validation: Ensure all assigned staff belong to this location (or are floating)
    assigned_staff_ids = set(data.assignments.values())
    staff_members = db.query(Staff).filter(Staff.id.in_(assigned_staff_ids)).all()
    
    for s in staff_members:
        if s.assigned_location_id and s.assigned_location_id != template.program_location_id:
             raise HTTPException(
                status_code=400, 
                detail=f"Staff {s.first_name} {s.last_name} is assigned to a different location"
            )
    
    try:
        current_date = data.start_date
        for _ in range(weeks):
            shift_start_date = current_date
            shift_end_date = shift_start_date + timedelta(days=1) if is_overnight else shift_start_date
            
            new_shift = Shift(
                shift_template_id=template.id,
                program_location_id=template.program_location_id,
                start_date=shift_start_date,
                start_time=start_time,
                end_date=shift_end_date,
                end_time=end_time,
                created_by=current_user.id  # HIPAA audit trail
            )
            db.add(new_shift)
            db.flush() # Get ID

            # Populate tasks for ALL positions in the template
            for position in template_positions:
                _populate_shift_tasks(db, new_shift.id, position.id)
            
            # Create assignments if provided
            if data.assignments:
                for pos_id, staff_id in data.assignments.items():
                    # Create assignment
                    assignment = ShiftAssignment(
                        shift_id=new_shift.id,
                        staff_id=staff_id,
                        shift_position_id=int(pos_id), # Ensure int key
                        assigned_at=datetime.utcnow(),
                        end_status_id=4  # 'pending'
                    )
                    db.add(assignment)

            created_shifts.append(new_shift)
            current_date = current_date + timedelta(weeks=1)
            
        db.commit()
        for s in created_shifts:
            db.refresh(s)
            
        return created_shifts
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value" in str(e.orig):
            raise HTTPException(status_code=409, detail="One or more shifts already exist for these dates")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/current")
def get_current_shift(request: Request, db: Session = Depends(get_db), staff: Staff = Depends(get_current_active_user)):
    """Return the current staff member's active shift, including tasks, assigned clients, and each client's behavior config.
    Only returns the ONE shift that is currently active (happening right now) or within a 30-minute grace period after ending.
    """
    
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    now = get_now(tz)
    today = now.date()
    current_time = now.time()
    
    # Grace period: 10 minutes after shift end
    GRACE_PERIOD_MINUTES = 10
    
    # FIRST: Check for any expired previous shifts and mark them as timeout
    # This runs BEFORE finding the current shift, so double-shifts are handled correctly
    from sqlalchemy import and_, or_
    
    expired_assignments = (
        db.query(ShiftAssignment)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .filter(
            ShiftAssignment.staff_id == staff.id,
            ShiftAssignment.end_status_id == 4  # 'pending' - not yet completed/timed out
        )
        .all()
    )
    
    for expired_assignment in expired_assignments:
        expired_shift = db.query(Shift).filter(Shift.id == expired_assignment.shift_id).first()
        if expired_shift:
            # Calculate when shift ended
            shift_end_dt = datetime.combine(expired_shift.end_date, expired_shift.end_time)
            if shift_end_dt.tzinfo is None:
                shift_end_dt = shift_end_dt.replace(tzinfo=tz)
            
            # If ended more than grace period ago, mark as timeout
            if now > shift_end_dt + timedelta(minutes=GRACE_PERIOD_MINUTES):
                # Mark assignment as timeout (system-initiated, so ended_by stays NULL)
                expired_assignment.end_status_id = 2  # 'timeout'
                expired_assignment.ended_at = now    # Set timestamp even for system actions
                
                # Get pending tasks to update and log to history
                pending_tasks = db.query(ShiftTaskStatus).filter(
                    ShiftTaskStatus.shift_id == expired_shift.id,
                    ShiftTaskStatus.shift_position_id == expired_assignment.shift_position_id,
                    ShiftTaskStatus.status_id == 1  # pending
                ).all()
                
                for task_status in pending_tasks:
                    old_status_id = task_status.status_id
                    task_status.status_id = 5  # not_completed
                    
                    # Log to history for HIPAA audit trail
                    history_entry = ShiftTaskStatusHistory(
                        shift_task_status_id=task_status.id,
                        from_status_id=old_status_id,
                        to_status_id=5,
                        changed_by=None,  # System-initiated (timeout)
                        notes="Auto-marked not_completed due to shift timeout"
                    )
                    db.add(history_entry)
    
    db.commit()

    # Find the CURRENT shift (the one happening right now or in grace period)
    # For same-day shifts: start_time <= current_time <= end_time on same date
    # For overnight shifts: either (started yesterday after start_time) OR (started today before end_time)
    # Grace period: also include shifts that ended within the last 10 minutes
    
    current_assignment = (
        db.query(ShiftAssignment, Shift, ShiftPosition)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .join(ShiftPosition, ShiftAssignment.shift_position_id == ShiftPosition.id)
        .filter(ShiftAssignment.staff_id == staff.id)
    )
    
    # Build time-aware filter for current shift with grace period
    from sqlalchemy import and_, or_
    
    # Calculate grace period end time
    grace_end_datetime = now - timedelta(minutes=GRACE_PERIOD_MINUTES)
    grace_end_date = grace_end_datetime.date()
    grace_end_time = grace_end_datetime.time()
    
    time_filter = or_(
        # Same-day shift: today between start and end time
        and_(
            Shift.start_date == today,
            Shift.end_date == today,
            Shift.start_time <= current_time,
            Shift.end_time >= current_time
        ),
        # Same-day shift in grace period: ended today within last 30 minutes
        and_(
            Shift.start_date == today,
            Shift.end_date == today,
            Shift.end_time < current_time,
            Shift.end_time >= grace_end_time
        ),
        # Overnight shift started yesterday, ends today (currently active)
        and_(
            Shift.start_date == today - timedelta(days=1),
            Shift.end_date == today,
            current_time <= Shift.end_time  # Before the end time
        ),
        # Overnight shift started yesterday, ended today but within grace period
        and_(
            Shift.start_date == today - timedelta(days=1),
            Shift.end_date == today,
            current_time > Shift.end_time,  # After the end time
            Shift.end_time >= grace_end_time  # But within grace period
        ),
        # Overnight shift starts today, ends tomorrow
        and_(
            Shift.start_date == today,
            Shift.end_date == today + timedelta(days=1),
            current_time >= Shift.start_time  # After the start time
        )
    )
    
    current_assignment = current_assignment.filter(time_filter).first()

    if not current_assignment:
        # Timeout check already happened at the start of this function
        raise HTTPException(status_code=404, detail="No current shift found for staff")

    assignment, shift, position = current_assignment

    # Get all tasks for this position
    # For shifts created via the new create_shift endpoint, all tasks are pre-populated in shift_task_status
    # For legacy/seed shifts, we need to merge shift_position_tasks (template) + shift_task_status (custom/completed)
    
    # 1. Get all tasks from shift_task_status (pre-populated template tasks + custom tasks)
    # Exclude deleted tasks (status_id = 4)
    existing_task_statuses = (
        db.query(ShiftTaskStatus, Task)
        .join(Task, ShiftTaskStatus.task_id == Task.id)
        .filter(
            ShiftTaskStatus.shift_id == shift.id,
            ShiftTaskStatus.shift_position_id == position.id,
            ShiftTaskStatus.status_id != 4  # Exclude deleted status
        )
        .all()
    )
    
    # 2. Get template tasks from shift_position_tasks (for backward compatibility with non-prepopulated shifts)
    template_tasks = (
        db.query(ShiftPositionTask, Task)
        .join(Task, ShiftPositionTask.task_id == Task.id)
        .filter(
            ShiftPositionTask.shift_position_id == position.id,
            Task.is_custom == False
        )
        .all()
    )
    
    # Build tasks_out, preferring shift_task_status when it exists
    tasks_out = []
    status_by_task_id = {sts.task_id: (sts, task) for sts, task in existing_task_statuses}
    
    # Add all tasks that have status records (pre-populated or custom)
    for sts, task in existing_task_statuses:
        tasks_out.append({
            "id": task.id,
            "name": task.name,
            "status_id": sts.status_id,
            "scheduled_start_time": sts.scheduled_start_time,
            "scheduled_end_time": sts.scheduled_end_time,
            "is_custom": task.is_custom,
            "completed_by_staff_id": sts.completed_by_staff_id,
            "completed_at": sts.completed_at,
            "notes": sts.notes,
        })
    
    # Add template tasks that don't have status records yet (backward compatibility)
    for pt, task in template_tasks:
        if task.id not in status_by_task_id:
            tasks_out.append({
                "id": task.id,
                "name": task.name,
                "status_id": 1,  # Pending
                "scheduled_start_time": pt.scheduled_start_time,
                "scheduled_end_time": pt.scheduled_end_time,
                "is_custom": False,
                "completed_by_staff_id": None,
                "completed_at": None,
                "notes": None,
            })

    # Clients assigned to this position
    position_clients = (
        db.query(ShiftPositionClient, Client)
        .join(Client, ShiftPositionClient.client_id == Client.id)
        .filter(ShiftPositionClient.shift_position_id == position.id)
        .all()
    )

    # Build base URL for media
    base_url = os.getenv("BASE_URL")
    if not base_url:
        scheme = "https" if request.url.scheme == "https" else "http"
        base_url = f"{scheme}://{request.headers.get('host', 'localhost:8443')}"

    clients_out = []
    for pc, client in position_clients:
        profile_image_url = None
        if client.profile_image_path:
            profile_image_url = f"{base_url}/uploads/clients/{client.profile_image_path}" if client.profile_image_path else None

        # Behavior config - get active version and its items
        active_config = (
            db.query(ClientBehaviorConfigVersion)
            .filter(
                ClientBehaviorConfigVersion.client_id == client.id,
                ClientBehaviorConfigVersion.is_active == True
            )
            .first()
        )
        
        # Get items from active config with behavior type info
        configs = []
        if active_config:
            configs = (
                db.query(ClientBehaviorConfigItem, BehaviorType)
                .join(BehaviorType, ClientBehaviorConfigItem.behavior_type_id == BehaviorType.id)
                .filter(ClientBehaviorConfigItem.config_version_id == active_config.id)
                .all()
            )
        
        # Get behavior occurrence counts for this shift
        from sqlalchemy import func
        occurrence_counts = (
            db.query(
                BehaviorTrackingRecord.behavior_type_id,
                func.sum(BehaviorTrackingRecord.recorded_value).label('count')
            )
            .filter(
                BehaviorTrackingRecord.shift_id == shift.id,
                BehaviorTrackingRecord.client_id == client.id
            )
            .group_by(BehaviorTrackingRecord.behavior_type_id)
            .all()
        )
        count_by_behavior = {bt_id: max(0, int(count or 0)) for bt_id, count in occurrence_counts}
        
        behaviors = [{
            "id": item.id,
            "behavior_type_id": btype.id,
            "behavior_name": btype.name,
            "target_value": item.target_value,
            "current_count": count_by_behavior.get(btype.id, 0),
        } for item, btype in configs]

        clients_out.append({
            "id": client.id,
            "first_name": client.first_name,
            "last_name": client.last_name,
            "profile_image_url": profile_image_url,
            "behaviors": behaviors,
        })

    # Get location info including group_number
    location = db.query(ProgramLocation).filter(ProgramLocation.id == shift.program_location_id).first()
    group_number = location.group_number if location else None
    
    # Calculate time until shift ends
    shift_end_datetime = datetime.combine(shift.end_date, shift.end_time)
    if shift_end_datetime.tzinfo is None:
        shift_end_datetime = shift_end_datetime.replace(tzinfo=tz)
    minutes_until_end = round((shift_end_datetime - now).total_seconds() / 60)
    
    # Check if this assignment has been ended
    has_ended = assignment.ended_at is not None
    
    response = {
        "shift": {
            "id": shift.id,
            "program_location_id": shift.program_location_id,
            "group_number": group_number,
            "start_date": shift.start_date,
            "start_time": shift.start_time,
            "end_date": shift.end_date,
            "end_time": shift.end_time,
        },
        "position": {
            "id": position.id,
            "name": position.position_name,
        },
        "assignment": {
            "id": assignment.id,
            "ended_at": assignment.ended_at.isoformat() if assignment.ended_at else None,
            "end_status_id": assignment.end_status_id,
            "has_ended": has_ended,
        },
        "time_info": {
            "minutes_until_end": minutes_until_end,
            "shift_ended": minutes_until_end < 0,
            "in_grace_period": minutes_until_end < 0 and minutes_until_end >= -10,  # 10 min grace
        },
        "tasks": tasks_out,
        "clients": clients_out,
    }
    
    # Log PHI access - we're returning client data AND potentially client-specific tasks
    from services.audit import AuditService
    client_ids = [c["id"] for c in clients_out]
    
    # Also collect client-specific task IDs
    client_task_ids = []
    for t in tasks_out:
        task = db.query(Task).filter(Task.id == t["id"]).first()
        if task and task.client_id:
            client_task_ids.append(t["id"])
    
    # Collect behavior config item IDs returned in the response
    behavior_config_ids = []
    for c in clients_out:
        for b in c.get("behaviors", []):
            behavior_config_ids.append(b["id"])
    
    if client_ids or client_task_ids or behavior_config_ids:
        audit = AuditService(db=db, user_id=staff.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access(
            "read", 
            "shift_current", 
            shift.id, 
            new_values={
                "client_ids": client_ids,
                "client_task_ids": client_task_ids,
                "all_task_ids": [t["id"] for t in tasks_out],
                "behavior_config_item_ids": behavior_config_ids
            }
        )
        db.commit()
    
    return response


@router.get("/unread")
def get_unread_shifts(
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all unread shifts for the current user."""
    from sqlalchemy import func
    
    # Get current timestamp
    now = datetime.now()
    
    # Find all locations where user has worked
    user_locations = (
        db.query(Shift.program_location_id.distinct())
        .join(ShiftAssignment)
        .filter(ShiftAssignment.staff_id == current_user.id)
        .all()
    )
    user_location_ids = [loc[0] for loc in user_locations]
    
    if not user_location_ids:
        return []
    
    # Get shifts user has already read
    read_shifts = (
        db.query(StaffLogReadStatus.log_shift_id)
        .filter(StaffLogReadStatus.staff_id == current_user.id)
        .all()
    )
    read_shift_ids = [rs[0] for rs in read_shifts]
    
    # Get all ended shifts at user's locations with logs
    shifts_query = (
        db.query(
            Shift.id.label("shift_id"),
            Shift.program_location_id,
            ProgramLocation.name.label("program_location_name"),
            Shift.start_date,
            Shift.start_time,
            Shift.end_date,
            Shift.end_time,
            func.count(ShiftDailyLog.id).label("log_count")
        )
        .join(ProgramLocation, ProgramLocation.id == Shift.program_location_id)
        .join(ShiftDailyLog, ShiftDailyLog.shift_id == Shift.id)
        .filter(Shift.program_location_id.in_(user_location_ids))
        .group_by(
            Shift.id,
            Shift.program_location_id,
            ProgramLocation.name,
            Shift.start_date,
            Shift.start_time,
            Shift.end_date,
            Shift.end_time
        )
        .having(func.count(ShiftDailyLog.id) > 0)
        .all()
    )
    
    result = []
    for shift in shifts_query:
        # Check if shift has ended
        shift_end = datetime.combine(shift.end_date, shift.end_time)
        if shift_end >= now:
            continue
            
        # Check if already read
        if shift.shift_id in read_shift_ids:
            continue
        
        # Calculate hours since ended
        hours_since = (now - shift_end).total_seconds() / 3600
        
        result.append({
            "shift_id": shift.shift_id,
            "program_location_id": shift.program_location_id,
            "program_location_name": shift.program_location_name,
            "start_date": shift.start_date.isoformat(),
            "start_time": shift.start_time.isoformat(),
            "end_date": shift.end_date.isoformat(),
            "end_time": shift.end_time.isoformat(),
            "log_count": shift.log_count,
            "hours_since_ended": hours_since
        })
    
    # Sort by most recent first
    result.sort(key=lambda x: (x["end_date"], x["end_time"]), reverse=True)
    
    return result


@router.get("/{shift_id}", response_model=ShiftOut)
def get_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get a specific shift with role-based access control:
    - Admin/Director: Any shift
    - Site Director: Shifts at their assigned location
    - DSP: Only shifts they were actually assigned to
    """
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Access control based on role
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: check if they were actually assigned to THIS specific shift
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Shift not found")  # Use 404 to avoid leaking existence
    
    return shift


@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def create_shift(
    data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Create a new shift instance. Site Directors can only create at their location."""
    
    # Site Directors can only create shifts at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != data.program_location_id:
            raise HTTPException(status_code=403, detail="You can only create shifts at your assigned location")
    
    # Validate template exists if provided
    template = None
    if data.shift_template_id:
        template = get_or_404(db, ShiftTemplate, data.shift_template_id)
    
    try:
        # Create shift
        new_shift = Shift(
            **data.model_dump(),
            created_by=current_user.id  # HIPAA audit trail
        )
        db.add(new_shift)
        db.flush()  # Get shift.id without committing
        
        # If shift was created from a template, pre-populate task statuses
        if template:
            # Get all positions for this template
            positions = db.query(ShiftPosition).filter(
                ShiftPosition.shift_template_id == template.id
            ).all()
            
            # For each position, copy its tasks to shift_task_status
            for position in positions:
                # Get all tasks assigned to this position
                position_tasks = db.query(ShiftPositionTask).filter(
                    ShiftPositionTask.shift_position_id == position.id
                ).all()
                
                # Create shift_task_status entry for each task
                for pt in position_tasks:
                    task_status = ShiftTaskStatus(
                        shift_id=new_shift.id,
                        task_id=pt.task_id,
                        shift_position_id=position.id,
                        status_id=1,  # Pending (default)
                        scheduled_start_time=pt.scheduled_start_time,
                        scheduled_end_time=pt.scheduled_end_time,
                        completed_by_staff_id=None,
                        completed_at=None,
                        notes=None
                    )
                    db.add(task_status)
        
        db.commit()
        db.refresh(new_shift)
        return new_shift
        
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift already exists")
        elif "violates check constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Data violates a table constraint")
        else:
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.put("/{shift_id}", response_model=ShiftOut)
def update_shift(
    shift_id: int,
    data: ShiftUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Update a shift. Site Directors can only update at their location."""
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Site Directors can only update shifts at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != shift.program_location_id:
            raise HTTPException(status_code=403, detail="You can only update shifts at your assigned location")
    
    update_data = data.model_dump(exclude_unset=True)
    
    # If start_date is being updated, auto-adjust end_date to maintain the same day relationship
    if 'start_date' in update_data:
        new_start = update_data['start_date']
        
        # Validation: Cannot move shift to the past
        if new_start < datetime.now().date():
            raise HTTPException(
                status_code=400, 
                detail="Cannot update shift to a past date"
            )

        old_start = shift.start_date
        old_end = shift.end_date
        
        # Calculate the original day difference (0 for same-day, 1 for overnight, etc.)
        day_diff = (old_end - old_start).days
        
        # Calculate what end_date should be based on new start
        new_end = new_start + timedelta(days=day_diff)
        
        # If end_date wasn't provided OR it's still the old value, auto-update it
        if 'end_date' not in update_data or update_data['end_date'] == old_end:
            update_data['end_date'] = new_end
    
    for key, value in update_data.items():
        setattr(shift, key, value)
    
    try:
        db.commit()
        db.refresh(shift)
        return shift
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift already exists")
        elif "violates check constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Data violates a table constraint")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/{shift_id}")
def delete_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Delete a shift. Site Directors can only delete at their location."""
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Site Directors can only delete shifts at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != shift.program_location_id:
            raise HTTPException(status_code=403, detail="You can only delete shifts at your assigned location")
    
    # Check for PENDING assignments (cancelled assignments don't block cancellation)
    pending_assignments = db.query(ShiftAssignment).filter(
        ShiftAssignment.shift_id == shift_id,
        ShiftAssignment.end_status_id == 4  # Only pending
    ).first()
    
    if pending_assignments:
        raise HTTPException(
            status_code=409, 
            detail="Cannot cancel shift with active assignments. Remove all assignments first."
        )
    
    # Soft delete: mark as cancelled instead of removing from database (HIPAA compliance)
    shift.cancelled_at = datetime.now()
    shift.cancelled_by = current_user.id
    
    db.commit()
    return {"message": f"Shift {shift_id} cancelled"}


@router.post("/{shift_id}/end", response_model=EndShiftResponse)
def end_shift(
    shift_id: int,
    data: EndShiftRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """End a shift by submitting explanations for incomplete tasks.
    
    Records the explanation in the notes field of each incomplete task's status record.
    Returns a summary of all tasks with their completion status.
    """
    from services.audit import AuditService
    # Verify shift exists
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Verify user is assigned to this shift
    assignment = (
        db.query(ShiftAssignment)
        .filter(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.staff_id == current_user.id
        )
        .first()
    )
    
    if not assignment:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this shift"
        )
    
    # Check if shift has already been ended by this user
    if assignment.ended_at is not None:
        raise HTTPException(
            status_code=400,
            detail="You have already ended this shift"
        )
    
    # Get all task statuses for this shift and position
    task_statuses = (
        db.query(ShiftTaskStatus, Task)
        .join(Task, ShiftTaskStatus.task_id == Task.id)
        .filter(
            ShiftTaskStatus.shift_id == shift_id,
            ShiftTaskStatus.shift_position_id == assignment.shift_position_id,
            ShiftTaskStatus.status_id != 4  # Exclude deleted tasks
        )
        .all()
    )
    
    # Build a map of task_id to explanation
    explanations_map = {exp.task_id: exp.explanation for exp in data.task_explanations}
    
    # Collect incomplete tasks (only non-custom tasks require explanations)
    incomplete_tasks = []
    for sts, task in task_statuses:
        if sts.status_id != 2:  # Not completed
            incomplete_tasks.append((sts, task))
    
    # Validate that all incomplete NON-CUSTOM tasks have explanations
    # Custom tasks are optional, so they don't require explanations
    missing_explanations = []
    for sts, task in incomplete_tasks:
        if not task.is_custom and task.id not in explanations_map:
            missing_explanations.append(task.name)
    
    if missing_explanations:
        raise HTTPException(
            status_code=400,
            detail=f"Missing explanations for incomplete tasks: {', '.join(missing_explanations)}"
        )
    
    # Record explanations for incomplete tasks and update status to incomplete_explained
    for sts, task in incomplete_tasks:
        explanation = explanations_map.get(task.id)
        if explanation:
            sts.notes = f"End shift note: {explanation}"
            sts.status_id = 6  # 'incomplete_explained'
    
    # Mark assignment as ended - determine if on-time or late
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    now = datetime.now(tz)
    shift_end_dt = datetime.combine(shift.end_date, shift.end_time)
    if shift_end_dt.tzinfo is None:
        shift_end_dt = shift_end_dt.replace(tzinfo=tz)
    
    assignment.ended_at = now
    if now <= shift_end_dt:
        assignment.end_status_id = 1  # 'completed' (on time)
    else:
        assignment.end_status_id = 3  # 'completed_late' (during grace period)
    
    try:
        # Log end shift event
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access(
            "update", 
            "shift_assignments", 
            assignment.id, 
            new_values={
                "shift_id": shift_id, 
                "action": "end_shift",
                "completed_tasks": sum(1 for sts, _ in task_statuses if sts.status_id == 2),
                "incomplete_tasks": len(task_statuses) - sum(1 for sts, _ in task_statuses if sts.status_id == 2)
            }
        )
        
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save task explanations")
    
    # Build response
    completed_count = sum(1 for sts, _ in task_statuses if sts.status_id == 2)
    incomplete_count = len(task_statuses) - completed_count
    
    task_summaries = [
        EndShiftTaskSummary(
            task_id=task.id,
            task_name=task.name,
            is_completed=(sts.status_id == 2),
            explanation=explanations_map.get(task.id) if sts.status_id != 2 else None
        )
        for sts, task in task_statuses
    ]
    
    return EndShiftResponse(
        success=True,
        message="Shift ended successfully",
        shift_id=shift_id,
        total_tasks=len(task_statuses),
        completed_tasks=completed_count,
        incomplete_tasks=incomplete_count,
        tasks=task_summaries
    )


# =============================================
# SHIFT ASSIGNMENTS
# =============================================

@router.get("/{shift_id}/assignments", response_model=list[ShiftAssignmentOut])
def get_shift_assignments(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get all assignments for a shift. Access follows shift scoping rules."""
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Apply same access control as GET /{shift_id}
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: check if they were actually assigned to THIS specific shift
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Shift not found")
    
    return db.query(ShiftAssignment).filter(ShiftAssignment.shift_id == shift_id).all()


@router.get("/{shift_id}/available-staff")
def get_available_staff_for_shift(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get staff members available for this shift (not assigned to overlapping shifts).
    
    Returns active staff at the shift's location who don't have pending assignments
    to any other shift that overlaps with this one.
    Site Directors see only staff at their role level or below.
    Role hierarchy: Admin > Director > Site Director > DSP
    """
    from models import StaffRole
    
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Build base query: active staff joined with StaffRole
    query = db.query(Staff, StaffRole.role_name).join(
        StaffRole, Staff.role_id == StaffRole.id
    ).filter(Staff.is_active == True)
    
    # Filter: staff at this shift's location OR floating staff (no assigned location)
    query = query.filter(
        or_(
            Staff.assigned_location_id == None,
            Staff.assigned_location_id == shift.program_location_id
        )
    )
    
    # Role hierarchy filtering - each role sees their level and below
    if current_user.role_id == ROLE_DIRECTOR:
        query = query.filter(Staff.role_id >= ROLE_DIRECTOR)  # role_id >= 2
    elif current_user.role_id == ROLE_SITE_DIRECTOR:
        query = query.filter(Staff.role_id >= ROLE_SITE_DIRECTOR)  # role_id >= 3
    # Admin sees everyone (no filter)
    
    rows = query.all()
    
    # Filter out staff who have overlapping assignments
    available_staff = []
    for staff_member, role_name in rows:
        if not _check_for_overlapping_assignments(db, staff_member.id, shift):
            available_staff.append({
                "id": staff_member.id,
                "first_name": staff_member.first_name,
                "last_name": staff_member.last_name,
                "role_name": role_name,
                "is_active": staff_member.is_active,
                "assigned_location_id": staff_member.assigned_location_id
            })
    
    return available_staff


@router.get("/templates/{template_id}/available-staff")
def get_available_staff_for_template(
    template_id: int,
    start_date: str,  # Query param: YYYY-MM-DD
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get staff available for a shift created from this template on the given date.
    
    Used during shift creation to filter out unavailable staff.
    """
    from datetime import datetime
    
    template = get_or_404(db, ShiftTemplate, template_id, detail="Template not found")
    
    # Parse the start date
    try:
        shift_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Calculate end date based on overnight flag
    if template.is_overnight:
        from datetime import timedelta
        shift_end_date = shift_start_date + timedelta(days=1)
    else:
        shift_end_date = shift_start_date
    
    # Create a "virtual" shift object for overlap checking
    class VirtualShift:
        def __init__(self, start_date, start_time, end_date, end_time, id=None):
            self.id = id
            self.start_date = start_date
            self.start_time = start_time
            self.end_date = end_date
            self.end_time = end_time
    
    virtual_shift = VirtualShift(
        start_date=shift_start_date,
        start_time=template.start_time,
        end_date=shift_end_date,
        end_time=template.end_time
    )
    
    from models import StaffRole
    
    # Build base query: active staff joined with StaffRole
    query = db.query(Staff, StaffRole.role_name).join(
        StaffRole, Staff.role_id == StaffRole.id
    ).filter(Staff.is_active == True)
    
    # Filter: staff at this template's location OR floating staff (no assigned location)
    query = query.filter(
        or_(
            Staff.assigned_location_id == None,
            Staff.assigned_location_id == template.program_location_id
        )
    )
    
    # Role hierarchy filtering - each role sees their level and below
    if current_user.role_id == ROLE_DIRECTOR:
        query = query.filter(Staff.role_id >= ROLE_DIRECTOR)  # role_id >= 2
    elif current_user.role_id == ROLE_SITE_DIRECTOR:
        query = query.filter(Staff.role_id >= ROLE_SITE_DIRECTOR)  # role_id >= 3
    # Admin sees everyone (no filter)
    
    rows = query.all()
    
    # Filter out staff who have overlapping assignments
    available_staff = []
    for staff_member, role_name in rows:
        if not _check_for_overlapping_assignments(db, staff_member.id, virtual_shift):
            available_staff.append({
                "id": staff_member.id, 
                "first_name": staff_member.first_name, 
                "last_name": staff_member.last_name, 
                "role_name": role_name,
                "is_active": staff_member.is_active,
                "assigned_location_id": staff_member.assigned_location_id
            })
    
    return available_staff

def _check_for_overlapping_assignments(db: Session, staff_id: int, target_shift: Shift) -> bool:
    """Check if staff member has any overlapping shift assignments.
    Returns True if there's an overlap, False otherwise.
    Only checks PENDING assignments (end_status_id = 4).
    """
    from datetime import datetime, timedelta
    
    # Get all PENDING shift assignments for this staff member (not completed/deleted)
    existing_assignments = (
        db.query(ShiftAssignment, Shift)
        .join(Shift, ShiftAssignment.shift_id == Shift.id)
        .filter(
            ShiftAssignment.staff_id == staff_id,
            ShiftAssignment.end_status_id == 4  # Only check pending assignments
        )
        .all()
    )
    
    for assignment, existing_shift in existing_assignments:
        # Skip if this is the exact same shift (shouldn't happen due to unique constraint, but safety check)
        if existing_shift.id == target_shift.id:
            continue
        
        # Check for date/time overlap
        if _shifts_overlap(existing_shift, target_shift):
            return True
    
    return False


def _shifts_overlap(shift1: Shift, shift2: Shift) -> bool:
    """Check if two shifts overlap in time.
    Handles same-day and overnight shifts.
    """
    from datetime import datetime, timedelta
    
    # Convert to datetime for comparison
    # Shift 1
    start1 = datetime.combine(shift1.start_date, shift1.start_time)
    end1 = datetime.combine(shift1.end_date, shift1.end_time)
    
    # Shift 2
    start2 = datetime.combine(shift2.start_date, shift2.start_time)
    end2 = datetime.combine(shift2.end_date, shift2.end_time)
    
    # Two time ranges overlap if:
    # start1 < end2 AND start2 < end1
    return start1 < end2 and start2 < end1


def _populate_shift_tasks(db: Session, shift_id: int, shift_position_id: int):
    """Helper to populate shift_task_status entries when an assignment is made"""
    position_tasks = db.query(ShiftPositionTask).filter(ShiftPositionTask.shift_position_id == shift_position_id).all()
    
    for pt in position_tasks:
        exists = db.query(ShiftTaskStatus).filter(
            ShiftTaskStatus.shift_id == shift_id,
            ShiftTaskStatus.shift_position_id == shift_position_id,
            ShiftTaskStatus.task_id == pt.task_id
        ).first()
        
        if not exists:
            status = ShiftTaskStatus(
                shift_id=shift_id,
                task_id=pt.task_id,
                shift_position_id=shift_position_id,
                status_id=1, # Pending
                scheduled_end_time=pt.scheduled_end_time
            )
            db.add(status)


@router.put("/assignments/{assignment_id}", response_model=ShiftAssignmentOut)
def update_shift_assignment(
    assignment_id: int,
    data: ShiftAssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Update a shift assignment. Site Directors can only update assignments at their location."""
    assignment = get_or_404(db, ShiftAssignment, assignment_id, detail="Assignment not found")
    
    # Get the shift to check location
    shift = db.query(Shift).filter(Shift.id == assignment.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    # Site Directors can only update assignments at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: assignment not at your location")
    
    # Validation: If updating staff_id, ensure new staff belongs to location
    if data.staff_id:
        new_staff = get_or_404(db, Staff, data.staff_id, detail="Staff member not found")
        
        if new_staff.assigned_location_id and new_staff.assigned_location_id != shift.program_location_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Staff {new_staff.first_name} {new_staff.last_name} is assigned to a different location"
            )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, key, value)
    
    try:
        db.commit()
        db.refresh(assignment)
        return assignment
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="A record with these values already exists")
        elif "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Referenced record does not exist")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/assignments/{assignment_id}")
def delete_shift_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Soft-delete a shift assignment for HIPAA compliance. Site Directors can only delete assignments at their assigned location."""
    from datetime import datetime
    
    assignment = get_or_404(db, ShiftAssignment, assignment_id, detail="Assignment not found")
    
    # Site Directors: verify assignment is at their location
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        from models import Shift
        shift = db.query(Shift).filter(Shift.id == assignment.shift_id).first()
        if shift and shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="You can only delete assignments at your assigned location")
    
    # Soft delete: mark as cancelled instead of removing from database
    assignment.ended_at = datetime.now()
    assignment.ended_by = current_user.id  # HIPAA audit trail
    assignment.end_status_id = 5  # 'cancelled'
    
    try:
        db.commit()
        return {"message": f"Assignment {assignment_id} cancelled"}
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred")



# =============================================
# SHIFT TASK STATUS
# =============================================

@router.get("/task-status/{status_id}/history", response_model=list[ShiftTaskStatusHistoryOut])
def get_task_status_history(
    status_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Get complete audit history for a task status (who changed what and when)"""
    from services.audit import AuditService
    
    # Verify task status exists
    task_status = get_or_404(db, ShiftTaskStatus, status_id, detail="Task status not found")
    
    # Get the shift to verify access
    shift = db.query(Shift).filter(Shift.id == task_status.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    # Access control - same as GET /{shift_id}
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: must be assigned to this specific shift
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift.id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Task status not found")
    
    # Get the task to check if it's client-specific
    task = db.query(Task).filter(Task.id == task_status.task_id).first()
    
    # Get all history entries for this task status
    history = db.query(ShiftTaskStatusHistory).filter(
        ShiftTaskStatusHistory.shift_task_status_id == status_id
    ).order_by(ShiftTaskStatusHistory.changed_at.desc()).all()
    
    # Log PHI access if client-specific task
    if task and task.client_id:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read", "shift_task_status_history", status_id, new_values={"client_id": task.client_id, "task_id": task.id})
        db.commit()
    
    return history


@router.get("/{shift_id}/task-status", response_model=list[ShiftTaskStatusOut])
def get_shift_task_statuses(
    shift_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get all task statuses for a shift with access control:
    - Admin/Director: Any shift
    - Site Director: Shifts at their assigned location
    - DSP: Only shifts they were actually assigned to
    """
    from services.audit import AuditService
    
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Access control
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: must be assigned to THIS specific shift
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Shift not found")
    
    task_statuses = db.query(ShiftTaskStatus).filter(ShiftTaskStatus.shift_id == shift_id).all()
    
    # Enrich with task names and collect client_ids
    result = []
    client_ids = set()
    for ts in task_statuses:
        task = db.query(Task).filter(Task.id == ts.task_id).first()
        if task and task.client_id:
            client_ids.add(task.client_id)
        ts_dict = {
            "id": ts.id,
            "shift_id": ts.shift_id,
            "task_id": ts.task_id,
            "shift_position_id": ts.shift_position_id,
            "status_id": ts.status_id,
            "scheduled_start_time": ts.scheduled_start_time,
            "scheduled_end_time": ts.scheduled_end_time,
            "completed_by_staff_id": ts.completed_by_staff_id,
            "completed_at": ts.completed_at,
            "notes": ts.notes,
            "task_name": task.name if task else None
        }
        result.append(ts_dict)
    
    # Log PHI access if any client-specific tasks
    if client_ids:
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("read_list", "shift_task_status", None, new_values={"shift_id": shift_id, "client_ids": list(client_ids)})
        db.commit()
    
    return result


@router.put("/task-status/{status_id}", response_model=ShiftTaskStatusOut)
def update_shift_task_status(
    status_id: int, 
    data: ShiftTaskStatusUpdate, 
    request: Request,
    db: Session = Depends(get_db), 
    current_user: Staff = Depends(get_current_active_user)
):
    """Update a shift task status and create audit history entry
    
    Only allows updating status_id, notes, and scheduling times.
    Structural fields (shift_id, task_id, shift_position_id) cannot be changed.
    
    When status changes:
    - Creates history entry for accountability (HIPAA compliance)
    - Records from_status_id → to_status_id transition
    - If status_id=2 (Completed): sets completed_by_staff_id and completed_at
    - If status_id=1 (Pending): clears completed_by_staff_id and completed_at
    """
    from services.audit import AuditService
    
    tz = ZoneInfo(os.getenv("TZ", "America/New_York"))
    task_status = get_or_404(db, ShiftTaskStatus, status_id, detail="Task status not found")
    
    # Verify user has access to the shift
    shift = db.query(Shift).filter(Shift.id == task_status.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift.id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Task status not found")
    
    # Prevent changing structural fields (would break audit trail and data integrity)
    if data.shift_id is not None and data.shift_id != task_status.shift_id:
        raise HTTPException(status_code=400, detail="Cannot change shift_id - create a new task status instead")
    if data.task_id is not None and data.task_id != task_status.task_id:
        raise HTTPException(status_code=400, detail="Cannot change task_id - create a new task status instead")
    if data.shift_position_id is not None and data.shift_position_id != task_status.shift_position_id:
        raise HTTPException(status_code=400, detail="Cannot change shift_position_id - create a new task status instead")

    # Get old status for history
    old_status_id = task_status.status_id
    new_status_id = data.status_id if data.status_id is not None else old_status_id
    
    # Update only allowed fields (status_id, notes, scheduling times)
    update_data = data.model_dump(exclude_unset=True, exclude={'shift_id', 'task_id', 'shift_position_id', 'completed_by_staff_id', 'completed_at'})
    for key, value in update_data.items():
        setattr(task_status, key, value)
    
    # Auto-set completion fields based on status
    if new_status_id == 2:  # Completed status
        task_status.completed_by_staff_id = current_user.id
        task_status.completed_at = datetime.now(tz)
    elif new_status_id == 1:  # Pending status
        task_status.completed_by_staff_id = None
        task_status.completed_at = None
    elif new_status_id == 4:  # Deleted status
        # If this is a custom task, also soft-delete it from the tasks table
        task = db.query(Task).filter(Task.id == task_status.task_id).first()
        if task and task.is_custom:
            task.is_active = False
    
    try:
        db.commit()
        db.refresh(task_status)
        
        # Create history entry for audit trail (if status changed)
        if old_status_id != new_status_id:
            history_entry = ShiftTaskStatusHistory(
                shift_task_status_id=task_status.id,
                from_status_id=old_status_id,
                to_status_id=new_status_id,
                changed_by=current_user.id,
                completed_by_staff_id=task_status.completed_by_staff_id if new_status_id == 2 else None,
                notes=data.notes if hasattr(data, 'notes') else None
            )
            db.add(history_entry)
            
            # Log PHI access if task is client-specific
            task = db.query(Task).filter(Task.id == task_status.task_id).first()
            if task and task.client_id:
                audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
                audit.log_data_access("update", "shift_task_status", task_status.id, new_values={"client_id": task.client_id, "from_status": old_status_id, "to_status": new_status_id})
            
            db.commit()
        
        return task_status
        
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift task status already exists")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


# =============================================
# SHIFT DAILY LOGS
# =============================================

@router.get("/{shift_id}/logs")
def get_shift_logs(
    shift_id: int, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get all daily logs for a shift with access control:
    - Admin/Director: Any shift
    - Site Director: Shifts at their assigned location
    - DSP: Shifts at locations where they have shift assignments
    """
    from services.audit import AuditService
    
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Access control
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: must be assigned to this specific shift
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == shift_id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Shift not found")
    
    logs = db.query(ShiftDailyLog).filter(ShiftDailyLog.shift_id == shift_id).all()
    
    # Log PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access("read_list", "shift_daily_logs", None, new_values={"shift_id": shift_id, "log_ids": [log.id for log in logs]})
    db.commit()
    
    result = []
    for log in logs:
        log_dict = {
            "id": log.id,
            "shift_id": log.shift_id,
            "staff_id": log.staff_id,
            "category_id": log.category_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "payload": log.payload,
            "staff_name": None,
            "category_name": None
        }
        
        if log.staff_id:
            staff = db.query(Staff).filter(Staff.id == log.staff_id).first()
            if staff:
                log_dict["staff_name"] = f"{staff.first_name} {staff.last_name}"
        
        if log.category_id:
            category = db.query(LogCategory).filter(LogCategory.id == log.category_id).first()
            if category:
                log_dict["category_name"] = category.name
        
        result.append(log_dict)
    
    return result


@router.get("/location/{location_id}/logs")
def get_location_logs(
    location_id: int, 
    request: Request,
    group_number: int | None = None, 
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Get all daily logs for a program location with access control:
    - Admin/Director: Any location
    - Site Director: Their assigned location only
    - DSP: Locations where they have shift assignments
    
    Args:
        location_id: The program_location_id 
        group_number: Optional group number for dayhab filtering
    
    Returns:
        All logs from shifts at this location, grouped by date
    """
    from services.audit import AuditService
    
    # Access control
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: location not assigned to you")
    elif current_user.role_id == ROLE_DSP:
        # DSP: check if they have any shift assignments at this location
        has_access = db.query(ShiftAssignment).join(
            Shift, ShiftAssignment.shift_id == Shift.id
        ).filter(
            ShiftAssignment.staff_id == current_user.id,
            Shift.program_location_id == location_id,
            Shift.cancelled_at.is_(None)
        ).first()
        
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied: no shift assignments at this location")

    # Get all shifts for this location
    shifts_query = db.query(Shift).filter(Shift.program_location_id == location_id)
    
    # If group_number is provided, filter by matching location's group_number
    if group_number is not None:
        # Verify the location has this group_number
        location = db.query(ProgramLocation).filter(ProgramLocation.id == location_id).first()
        if not location or location.group_number != group_number:
            return []
    
    shifts = shifts_query.all()
    shift_ids = [s.id for s in shifts]
        
    if not shift_ids:
        return []
    
    # Get all logs from these shifts
    logs = (
        db.query(ShiftDailyLog)
        .filter(ShiftDailyLog.shift_id.in_(shift_ids))
        .order_by(desc(ShiftDailyLog.created_at))
        .all()
    )
    
    # Log PHI access
    audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    audit.log_data_access(
        "read_list", 
        "shift_daily_logs", 
        None, 
        new_values={
            "location_id": location_id, 
            "group_number": group_number,
            "count": len(logs)
        }
    )
    db.commit()
    
    result = []
    for log in logs:
        # Get shift details
        shift = db.query(Shift).filter(Shift.id == log.shift_id).first()
        
        log_dict = {
            "id": log.id,
            "shift_id": log.shift_id,
            "staff_id": log.staff_id,
            "category_id": log.category_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
            "payload": log.payload,
            "staff_name": None,
            "shift_start_time": shift.start_time.isoformat() if shift and shift.start_time else None,
            "shift_end_time": shift.end_time.isoformat() if shift and shift.end_time else None,
            "shift_date": shift.start_date.isoformat() if shift and shift.start_date else None
        }
        
        if log.staff_id:
            staff = db.query(Staff).filter(Staff.id == log.staff_id).first()
            if staff:
                log_dict["staff_name"] = f"{staff.first_name} {staff.last_name}"
        
        result.append(log_dict)
    
    return result


@router.post("/logs", response_model=ShiftDailyLogOut, status_code=status.HTTP_201_CREATED)
def create_shift_log(
    data: ShiftDailyLogCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """Create a new daily log entry for a shift"""
    from services.audit import AuditService
    
    # Verify user has access to the shift
    shift = get_or_404(db, Shift, data.shift_id, detail="Shift not found")
    
    if current_user.role_id == ROLE_SITE_DIRECTOR and current_user.assigned_location_id:
        if shift.program_location_id != current_user.assigned_location_id:
            raise HTTPException(status_code=403, detail="Access denied: shift not at your location")
    elif current_user.role_id == ROLE_DSP:
        # DSP: must be assigned to this specific shift
        was_assigned = db.query(ShiftAssignment).filter(
            ShiftAssignment.shift_id == data.shift_id,
            ShiftAssignment.staff_id == current_user.id
        ).first()
        if not was_assigned:
            raise HTTPException(status_code=404, detail="Shift not found")
    
    try:
        new_log = ShiftDailyLog(**data.model_dump())
        # Ensure staff_id is set to current user if not provided (though safely handle if model allows)
        if not new_log.staff_id:
             new_log.staff_id = current_user.id
             
        db.add(new_log)
        db.flush() # Get ID
        
        # Log creation
        audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
        audit.log_data_access("create", "shift_daily_logs", new_log.id, new_values=data.model_dump())
        
        db.commit()
        db.refresh(new_log)
        return new_log
    except IntegrityError as e:
        db.rollback()
        if "foreign key constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Referenced record does not exist")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.delete("/logs/{log_id}")
def delete_shift_log(
    log_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """
    DISABLED: Shift logs are immutable for HIPAA compliance.
    Delete a daily log entry. Site Directors can only delete logs at their assigned location.
    """
    raise HTTPException(status_code=405, detail="Shift logs are immutable and cannot be deleted.")
    # from services.audit import AuditService
    # log = get_or_404(db, ShiftDailyLog, log_id, detail="Log not found")
    
    # # Log deletion
    # audit = AuditService(db=db, user_id=current_user.id, ip=getattr(request.state, 'client_ip', None), user_agent=request.headers.get("user-agent"))
    # audit.log_data_access("delete", "shift_daily_logs", log.id, old_values={"payload": log.payload})

    
    # # Site Directors: verify log is at their location
    # if current_user.role_id == ROLE_SITE_DIRECTOR:
    #     from models import Shift
    #     shift = db.query(Shift).filter(Shift.id == log.shift_id).first()
    #     if shift and shift.program_location_id != current_user.assigned_location_id:
    #         raise HTTPException(status_code=403, detail="You can only delete logs at your assigned location")
    
    # db.delete(log)
    # db.commit()
    # return {"message": f"Log {log_id} deleted"}


# =============================================
# STAFF LOG READ STATUS (UNREAD SHIFTS)
# =============================================

@router.post("/mark-read", status_code=status.HTTP_201_CREATED)
def mark_shift_as_read(
    data: MarkLogReadRequest,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(get_current_active_user)
):
    """
    Mark a shift's logs as read by the current user.
    """
    # Verify the shift exists
    shift = get_or_404(db, Shift, data.log_shift_id, detail="Shift not found")
    
    # Check if already marked as read
    existing = (
        db.query(StaffLogReadStatus)
        .filter(
            StaffLogReadStatus.staff_id == current_user.id,
            StaffLogReadStatus.log_shift_id == data.log_shift_id
        )
        .first()
    )
    
    if existing:
        return {"message": "Shift already marked as read"}
    
    # Create read status entry
    read_status = StaffLogReadStatus(
        staff_id=current_user.id,
        log_shift_id=data.log_shift_id,
        read_during_shift_id=data.read_during_shift_id,
        read_timestamp=datetime.now()
    )
    
    try:
        db.add(read_status)
        db.commit()
        return {"message": "Shift marked as read"}
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Shift already marked as read")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")


# =============================================
# SHIFT ASSIGNMENTS
# =============================================

@router.get("/{shift_id}/assignments", response_model=list[ShiftAssignmentOut])
def get_shift_assignments(
    shift_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Get all staff assignments for a specific shift"""
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Site Director check
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != shift.program_location_id:
            raise HTTPException(status_code=403, detail="Access forbidden: different location")
            
    return db.query(ShiftAssignment).filter(ShiftAssignment.shift_id == shift_id).all()


@router.post("/{shift_id}/assignments", response_model=ShiftAssignmentOut, status_code=status.HTTP_201_CREATED)
def create_shift_assignment_for_shift(
    shift_id: int,
    data: ShiftAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin", "director", "site_director"]))
):
    """Assign a staff member to a shift position"""
    shift = get_or_404(db, Shift, shift_id, detail="Shift not found")
    
    # Site Director check
    if current_user.role_id == ROLE_SITE_DIRECTOR:
        if current_user.assigned_location_id != shift.program_location_id:
            raise HTTPException(status_code=403, detail="Access forbidden: different location")
            
    # Verify position belongs to shift template
    # Note: For now we assume position exists, but ideally verify it matches shift pattern
    
    # Validation: Ensure staff belongs to this location (or is floating)
    assigned_staff = get_or_404(db, Staff, data.staff_id, detail="Staff member not found")
    if assigned_staff.assigned_location_id and assigned_staff.assigned_location_id != shift.program_location_id:
        raise HTTPException(
            status_code=400, 
            detail=f"Staff {assigned_staff.first_name} {assigned_staff.last_name} is assigned to a different location"
        )
    
    # Check for overlapping shifts
    overlapping = _check_for_overlapping_assignments(db, data.staff_id, shift)
    if overlapping:
        raise HTTPException(
            status_code=409, 
            detail=f"Staff member {assigned_staff.first_name} {assigned_staff.last_name} is already assigned to another shift that overlaps with this time slot."
        )
    
    try:
        new_assignment = ShiftAssignment(
            shift_id=shift_id,
            **data.model_dump(exclude={'shift_id'}),
            assigned_by=current_user.id,      # HIPAA audit trail
            end_status_id=4                   # 'pending'
        )
        db.add(new_assignment)
        
        # Populate tasks
        _populate_shift_tasks(db, shift_id, data.shift_position_id)
        
        db.commit()
        db.refresh(new_assignment)
        return new_assignment
    except IntegrityError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e.orig):
            raise HTTPException(status_code=409, detail="Staff member already assigned to this shift")
        else:
            raise HTTPException(status_code=500, detail="An unexpected error occurred")
