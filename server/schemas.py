from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, computed_field, EmailStr, field_validator, ConfigDict, model_validator
from datetime import date, datetime, time

# =============================================
# STAFF & LOCATIONS
# =============================================

class StaffRoleBase(BaseModel):
    role_name: str
    description: Optional[str] = None
    is_active: bool = True

class StaffRoleCreate(StaffRoleBase):
    pass

class StaffRoleUpdate(BaseModel):
    role_name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class StaffRoleOut(StaffRoleBase):
    id: int
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class StaffCreate(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    work_email: EmailStr
    work_phone: Optional[str] = None
    password: str
    role_id: int
    assigned_location_id: Optional[int] = None
    is_active: bool = True

class StaffResetPassword(BaseModel):
    password: str

class StaffUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    work_email: Optional[EmailStr] = None
    work_phone: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None

class StaffOut(BaseModel):
    id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    work_email: str
    work_phone: Optional[str] = None
    role_id: int
    role_name: Optional[str] = None
    assigned_location_id: Optional[int] = None
    profile_image_path: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class AddressBase(BaseModel):
    street_line_1: str = Field(..., min_length=1)
    street_line_2: str = '' 
    city: str = Field(..., min_length=1)
    state_province: str = Field(..., min_length=1)
    postal_code: str = Field(..., min_length=1)
    country: str = "USA"
    
    @field_validator('street_line_2', mode='before')
    @classmethod
    def normalize_street_line_2(cls, v):
        # This is still good! It converts incoming None/null to ''
        return v if v else ''

class AddressCreate(AddressBase):
    pass

class AddressUpdate(BaseModel):
    street_line_1: Optional[str] = None
    street_line_2: Optional[str] = None 
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    
    # Add the validator here too for update operations
    @field_validator('street_line_2', mode='before')
    @classmethod
    def normalize_street_line_2_update(cls, v):
        return v if v else ''


class AddressOut(AddressBase):
    id: int
    
    class Config:
        from_attributes = True

class LocationTypeBase(BaseModel):
    name: str

class LocationTypeCreate(LocationTypeBase):
    pass

class LocationTypeOut(LocationTypeBase):
    id: int
    
    class Config:
        from_attributes = True


class ProgramLocationBase(BaseModel):
    name: str
    location_type_id: int
    group_number: Optional[int] = None
    address_id: int  # Required
    is_active: bool = True

class ProgramLocationCreate(ProgramLocationBase):
    pass

class ProgramLocationUpdate(BaseModel):
    name: Optional[str] = None
    location_type_id: Optional[int] = None
    group_number: Optional[int] = None
    address_id: Optional[int] = None
    is_active: Optional[bool] = None

class ProgramLocationOut(ProgramLocationBase):
    id: int
    location_type: LocationTypeOut
    
    class Config:
        from_attributes = True


# =============================================
# CLIENTS
# =============================================

class ClientBase(BaseModel):
    # this does not include id because ids are assigned by the database & the ClientBase is used for creation & updates as well
    first_name: str = Field(..., min_length=1)
    middle_name: Optional[str] = None
    last_name: str = Field(..., min_length=1)
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    date_of_birth: date
    gender: Optional[str] = None
    race: Optional[str] = None
    height_feet: Optional[int] = None
    height_inches: Optional[float] = None
    medical_conditions: Optional[str] = None
    mobility_status: Optional[str] = None
    profile_image_path: Optional[str] = None
    is_active: bool = True

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    race: Optional[str] = None
    height_feet: Optional[int] = None
    height_inches: Optional[float] = None
    medical_conditions: Optional[str] = None
    mobility_status: Optional[str] = None
    profile_image_path: Optional[str] = None
    is_active: Optional[bool] = None

class ClientProgramEnrollmentSummary(BaseModel):
    program_location_id: int
    is_active: bool

    class Config:
        from_attributes = True

class ClientOut(ClientBase):
    id: int
    active_enrollments: list[ClientProgramEnrollmentSummary] = []
    
    @model_validator(mode='before')
    @classmethod
    def compute_active_enrollments(cls, data):
        # Handle ORM object (from SQLAlchemy)
        if hasattr(data, 'program_enrollments'):
            today = date.today()
            active = [
                {'program_location_id': e.program_location_id, 'is_active': True}
                for e in data.program_enrollments
                if e.end_date is None or e.end_date >= today
            ]
            # Convert ORM object to dict-like for Pydantic
            if hasattr(data, '__dict__'):
                result = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}
                result['active_enrollments'] = active
                return result
        return data
    
    class Config:
        from_attributes = True


class ClientContactBase(BaseModel):
    client_id: int
    contact_first_name: str = Field(..., min_length=1)
    contact_middle_name: Optional[str] = None
    contact_last_name: str = Field(..., min_length=1)
    contact_suffix_name: Optional[str] = None
    contact_phone_primary: str = Field(..., min_length=1)
    contact_phone_secondary: Optional[str] = None
    relationship: Optional[int] = None
    is_primary: bool = False
    address_id: Optional[int] = None

class ClientContactCreate(ClientContactBase):
    pass

class ClientContactUpdate(BaseModel):
    contact_first_name: Optional[str] = None
    contact_middle_name: Optional[str] = None
    contact_last_name: Optional[str] = None
    contact_suffix_name: Optional[str] = None
    contact_phone_primary: Optional[str] = None
    contact_phone_secondary: Optional[str] = None
    relationship: Optional[int] = None
    is_primary: Optional[bool] = None
    address_id: Optional[int] = None
    is_active: Optional[bool] = None

class ClientContactOut(ClientContactBase):
    id: int
    is_active: bool = True
    
    address: Optional[AddressOut] = None
    
    class Config:
        from_attributes = True


class ClientResidenceTypeBase(BaseModel):
    name: str
    is_active: bool = True

class ClientResidenceTypeCreate(ClientResidenceTypeBase):
    pass

class ClientResidenceTypeUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class ClientResidenceTypeOut(ClientResidenceTypeBase):
    id: int
    
    class Config:
        from_attributes = True


class ClientResidenceHistoryBase(BaseModel):
    client_id: int
    residence_type_id: int
    address_id: int
    start_date: date

class ClientResidenceHistoryCreate(ClientResidenceHistoryBase):
    pass

class ClientResidenceHistoryUpdate(BaseModel):
    residence_type_id: Optional[int] = None
    address_id: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class ClientResidenceHistoryOut(ClientResidenceHistoryBase):
    id: int
    end_date: Optional[date] = None
    end_status: Optional[str] = None
    created_by: Optional[int] = None  # HIPAA audit: who created this entry
    ended_by: Optional[int] = None    # HIPAA audit: who ended this residence
    created_at: datetime
    ended_at: Optional[datetime] = None  # HIPAA audit: exact time when ended
    
    address: Optional[AddressOut] = None
    residence_type: Optional[ClientResidenceTypeOut] = None
    
    class Config:
        from_attributes = True



class ClientProgramEnrollmentBase(BaseModel):
    client_id: int
    program_location_id: int
    start_date: date = Field(default_factory=date.today)

class ClientProgramEnrollmentCreate(ClientProgramEnrollmentBase):
    pass  # created_by is set by the API from current_user

class ClientProgramEnrollmentUpdate(BaseModel):
    """DISABLED: Enrollment records are immutable for HIPAA compliance."""
    pass  # This schema is kept for type compatibility but won't be used

class ClientProgramEnrollmentOut(ClientProgramEnrollmentBase):
    id: int
    end_date: Optional[date] = None
    end_status: Optional[str] = None
    created_by: Optional[int] = None  # HIPAA audit: who enrolled the client
    ended_by: Optional[int] = None    # HIPAA audit: who ended enrollment
    created_at: datetime
    ended_at: Optional[datetime] = None  # HIPAA audit: exact time when ended
    
    class Config:
        from_attributes = True


# =============================================
# TASKS & SHIFTS
# =============================================

class TaskCategoryBase(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    is_active: bool = True

    # Normalize and validate name (strip whitespace; disallow empty)
    @field_validator('name', mode='before')
    @classmethod
    def validate_name(cls, v: Optional[str]):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

class TaskCategoryCreate(TaskCategoryBase):
    pass

class TaskCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

    # If provided, enforce non-empty after trimming
    @field_validator('name', mode='before')
    @classmethod
    def validate_name_optional(cls, v: Optional[str]):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

class TaskCategoryOut(TaskCategoryBase):
    id: int
    
    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    category_id: Optional[int] = None
    client_id: Optional[int] = None  # NULL = global task, set = client-specific
    estimated_duration_minutes: Optional[int] = None
    is_active: bool = True

    @field_validator('name', mode='before')
    @classmethod
    def normalize_task_name(cls, v: Optional[str]):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    client_id: Optional[int] = None
    estimated_duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator('name', mode='before')
    @classmethod
    def normalize_task_name_optional(cls, v: Optional[str]):
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

class TaskOut(TaskBase):
    id: int
    is_custom: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TaskStatusTypeBase(BaseModel):
    name: str = Field(..., min_length=1)

class TaskStatusTypeCreate(TaskStatusTypeBase):
    pass

class TaskStatusTypeUpdate(BaseModel):
    name: Optional[str] = None

class TaskStatusTypeOut(TaskStatusTypeBase):
    id: int
    
    class Config:
        from_attributes = True


class ShiftTemplateBase(BaseModel):
    name: str
    start_day_of_week: int
    start_time: time
    end_time: time
    program_location_id: Optional[int] = None
    is_active: bool = True
    is_overnight: bool = False

class ShiftTemplateCreate(ShiftTemplateBase):
    pass

class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = None
    start_day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    program_location_id: Optional[int] = None
    is_active: Optional[bool] = None
    is_overnight: Optional[bool] = None

class ShiftTemplateOut(ShiftTemplateBase):
    id: int
    shift_positions: list["ShiftPositionOut"] = []
    
    class Config:
        from_attributes = True


class ShiftPositionClientBase(BaseModel):
    shift_position_id: int
    client_id: int

class ShiftPositionClientOut(ShiftPositionClientBase):
    id: int
    client: Optional["ClientOut"] = None
    
    class Config:
        from_attributes = True

class ShiftPositionBase(BaseModel):
    shift_template_id: int
    position_name: str
    description: Optional[str] = None

class ShiftPositionCreate(ShiftPositionBase):
    client_ids: list[int] = []

class ShiftPositionUpdate(BaseModel):
    position_name: Optional[str] = None
    description: Optional[str] = None
    client_ids: Optional[list[int]] = None

class ShiftPositionOut(ShiftPositionBase):
    id: int
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None
    archived_at: Optional[datetime] = None
    archived_by: Optional[int] = None
    
    class Config:
        from_attributes = True

    tasks: list["ShiftPositionTaskOut"] = []
    clients: list["ShiftPositionClientOut"] = []


class ShiftPositionTaskBase(BaseModel):
    shift_position_id: int
    task_id: int
    scheduled_end_time: Optional[time] = None

class ShiftPositionTaskCreate(ShiftPositionTaskBase):
    pass

class ShiftPositionTaskUpdate(BaseModel):
    shift_position_id: Optional[int] = None
    task_id: Optional[int] = None
    scheduled_end_time: Optional[time] = None

class ShiftPositionTaskOut(ShiftPositionTaskBase):
    id: int
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None
    archived_at: Optional[datetime] = None
    archived_by: Optional[int] = None
    task: Optional["TaskOut"] = None
    
    class Config:
        from_attributes = True


class ShiftBase(BaseModel):
    shift_template_id: Optional[int] = None
    program_location_id: Optional[int] = None
    start_date: date
    start_time: time
    end_date: date
    end_time: time

class ShiftCreate(ShiftBase):
    pass

class ShiftCreateFromTemplate(BaseModel):
    shift_template_id: int
    start_date: date
    repeat_weeks: Optional[int] = Field(1, ge=1, le=4)
    assignments: Dict[int, int] = {} # position_id -> staff_id

class ShiftUpdate(BaseModel):
    shift_template_id: Optional[int] = None
    program_location_id: Optional[int] = None
    start_date: Optional[date] = None
    start_time: Optional[time] = None
    end_date: Optional[date] = None
    end_time: Optional[time] = None

class ShiftOut(ShiftBase):
    id: int
    
    class Config:
        from_attributes = True


class ShiftAssignmentBase(BaseModel):
    shift_id: int
    staff_id: int
    shift_position_id: int

class ShiftAssignmentCreate(ShiftAssignmentBase):
    pass

class ShiftAssignmentUpdate(BaseModel):
    shift_id: Optional[int] = None
    staff_id: Optional[int] = None
    shift_position_id: Optional[int] = None

class ShiftAssignmentOut(ShiftAssignmentBase):
    id: int
    end_status_id: Optional[int] = None
    ended_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ShiftTaskStatusBase(BaseModel):
    shift_id: int
    task_id: int
    shift_position_id: int
    status_id: int = 1
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    completed_by_staff_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

class ShiftTaskStatusCreate(ShiftTaskStatusBase):
    pass

class ShiftTaskStatusUpdate(BaseModel):
    shift_id: Optional[int] = None
    task_id: Optional[int] = None
    shift_position_id: Optional[int] = None
    status_id: Optional[int] = None
    scheduled_start_time: Optional[time] = None
    scheduled_end_time: Optional[time] = None
    completed_by_staff_id: Optional[int] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None

class ShiftTaskStatusOut(ShiftTaskStatusBase):
    id: int
    task_name: Optional[str] = None  # Populated by endpoint when needed
    
    class Config:
        from_attributes = True


class ShiftTaskStatusHistoryBase(BaseModel):
    shift_task_status_id: int
    from_status_id: Optional[int] = None
    to_status_id: int
    changed_by: int
    notes: Optional[str] = None
    completed_by_staff_id: Optional[int] = None


class ShiftTaskStatusHistoryCreate(ShiftTaskStatusHistoryBase):
    pass


class ShiftTaskStatusHistoryOut(ShiftTaskStatusHistoryBase):
    id: int
    changed_at: datetime
    
    class Config:
        from_attributes = True


class ShiftDailyLogBase(BaseModel):
    shift_id: int
    staff_id: Optional[int] = None
    category_id: Optional[int] = None
    payload: Optional[dict[str, Any]] = None

class ShiftDailyLogCreate(ShiftDailyLogBase):
    pass

class ShiftDailyLogUpdate(BaseModel):
    staff_id: Optional[int] = None
    shift_id: Optional[int] = None
    category_id: Optional[int] = None
    payload: Optional[dict[str, Any]] = None

class ShiftDailyLogOut(ShiftDailyLogBase):
    id: int
    created_at: Optional[datetime] = None
    staff_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# =============================================
# LOG CATEGORIES
# =============================================

class LogCategoryBase(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = None
    display_order: int
    is_active: bool = True
    icon: str = Field(default='folder', max_length=50)
    form_schema: Optional[dict] = None

class LogCategoryCreate(LogCategoryBase):
    pass

class LogCategoryUpdate(BaseModel):
    key: Optional[str] = Field(None, min_length=1, max_length=64)
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    icon: Optional[str] = Field(None, max_length=50)
    form_schema: Optional[dict] = None

class LogCategoryOut(LogCategoryBase):
    id: int
    
    class Config:
        from_attributes = True


# =============================================
# STAFF LOG READ STATUS
# =============================================

class UnreadShiftOut(BaseModel):
    shift_id: int
    program_location_id: int
    program_location_name: str
    start_date: str
    start_time: str
    end_date: str
    end_time: str
    log_count: int
    hours_since_ended: float

class MarkLogReadRequest(BaseModel):
    log_shift_id: int
    read_during_shift_id: Optional[int] = None


# =============================================
# END SHIFT
# =============================================

class EndShiftTaskExplanation(BaseModel):
    """Explanation for an incomplete task when ending a shift"""
    task_id: int
    explanation: str = Field(..., min_length=1, max_length=500)

class EndShiftRequest(BaseModel):
    """Request body for ending a shift with task explanations"""
    task_explanations: list[EndShiftTaskExplanation] = []

class EndShiftTaskSummary(BaseModel):
    """Summary of a single task in the end shift response"""
    task_id: int
    task_name: str
    is_completed: bool
    explanation: Optional[str] = None

class EndShiftResponse(BaseModel):
    """Response after ending a shift"""
    success: bool
    message: str
    shift_id: int
    total_tasks: int
    completed_tasks: int
    incomplete_tasks: int
    tasks: list[EndShiftTaskSummary]





# =============================================
# BEHAVIOR TRACKING
# =============================================

class BehaviorTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class BehaviorTypeCreate(BehaviorTypeBase):
    pass

class BehaviorTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class BehaviorTypeOut(BehaviorTypeBase):
    id: int
    
    class Config:
        from_attributes = True


# Behavior Config Item schemas (individual behavior in a config version)
class BehaviorConfigItemBase(BaseModel):
    behavior_type_id: int
    target_value: Optional[int] = None
    notes: Optional[str] = None

class BehaviorConfigItemCreate(BehaviorConfigItemBase):
    pass

class BehaviorConfigItemOut(BehaviorConfigItemBase):
    id: int
    behavior_type: Optional[BehaviorTypeOut] = None
    
    class Config:
        from_attributes = True


# Config Version schemas (master version containing multiple behaviors)
class ConfigVersionBase(BaseModel):
    notes: Optional[str] = None

class ConfigVersionCreate(ConfigVersionBase):
    behavior_type_ids: list[int]  # List of behavior types to include in this version

class ConfigVersionOut(ConfigVersionBase):
    id: int
    client_id: int
    version: int
    is_active: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    items: list[BehaviorConfigItemOut] = []
    
    class Config:
        from_attributes = True


class BehaviorTrackingRecordBase(BaseModel):
    shift_id: Optional[int] = None
    staff_id: Optional[int] = None
    client_id: Optional[int] = None
    behavior_type_id: Optional[int] = None
    config_version_id: Optional[int] = None
    recorded_value: int
    notes: Optional[str] = None

class BehaviorTrackingRecordCreate(BehaviorTrackingRecordBase):
    pass

class BehaviorTrackingRecordUpdate(BaseModel):
    shift_id: Optional[int] = None
    staff_id: Optional[int] = None
    client_id: Optional[int] = None
    behavior_type_id: Optional[int] = None
    recorded_value: Optional[int] = None
    notes: Optional[str] = None

class BehaviorTrackingRecordOut(BehaviorTrackingRecordBase):
    id: int
    recorded_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class BehaviorTrackingRecordWithDetails(BehaviorTrackingRecordOut):
    behavior_type: Optional[BehaviorTypeOut] = None
    staff: Optional[StaffOut] = None
    
    class Config:
        from_attributes = True


class ClientProtocolAssignmentBase(BaseModel):
    client_id: int
    protocol_id: int
    is_active: bool = True

class ClientProtocolAssignmentCreate(ClientProtocolAssignmentBase):
    pass

class ClientProtocolAssignmentUpdate(BaseModel):
    is_active: Optional[bool] = None

class ClientProtocolAssignmentOut(ClientProtocolAssignmentBase):
    id: int
    assigned_by: Optional[int] = None
    has_customization: bool
    
    class Config:
        from_attributes = True





# =============================================
# DOCUMENTS & COMMUNICATIONS
# =============================================

class DocumentCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class DocumentCategoryCreate(DocumentCategoryBase):
    pass

class DocumentCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class DocumentCategoryOut(DocumentCategoryBase):
    id: int
    
    class Config:
        from_attributes = True


class DocumentTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: int
    subcategory_id: Optional[int] = None
    icon: str = "doc.text"
    revision_interval_days: int = 365
    form_schema: dict
    is_archived: bool = False

class DocumentTemplateCreate(DocumentTemplateBase):
    created_by: Optional[int] = None

class DocumentTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    subcategory_id: Optional[int] = None
    icon: Optional[str] = None
    revision_interval_days: Optional[int] = None
    form_schema: Optional[dict] = None
    is_archived: Optional[bool] = None

class DocumentTemplateOut(DocumentTemplateBase):
    id: int
    version: Optional[int] = None
    created_by: Optional[int] = None
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ClientDocumentCreate(BaseModel):
    template_id: int
    values: dict
    revision_notes: Optional[str] = None


class ClientUpdateBase(BaseModel):
    client_id: int
    content: str

class ClientUpdateCreate(ClientUpdateBase):
    created_by: Optional[int] = None

class ClientUpdateUpdate(BaseModel):
    content: Optional[str] = None
    is_archived: Optional[bool] = None

class ClientUpdateOut(ClientUpdateBase):
    id: int
    created_by: Optional[int] = None
    is_archived: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True