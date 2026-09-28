from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Text, Numeric, Time, CheckConstraint, UniqueConstraint, Index, text, func
from sqlalchemy.dialects.postgresql import JSONB, CITEXT
from sqlalchemy.orm import relationship as sa_relationship
from database import Base

# =============================================
# STAFF & LOCATIONS
# =============================================

class StaffRole(Base):
    __tablename__ = "staff_roles"
    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(CITEXT, unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now()) 
    staff = sa_relationship("Staff", back_populates="role")


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(CITEXT, nullable=False)
    middle_name = Column(CITEXT)
    last_name = Column(CITEXT, nullable=False)
    preferred_name = Column(CITEXT)
    suffix = Column(CITEXT)
    work_email = Column(CITEXT, unique=True, nullable=False)
    work_phone = Column(String(20))
    password_hash = Column(String(255), nullable=False)
    must_change_password = Column(Boolean, default=True)
    role_id = Column(Integer, ForeignKey("staff_roles.id"), nullable=False)
    assigned_location_id = Column(Integer, ForeignKey("program_locations.id"))
    profile_image_path = Column(String(500))
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    role = sa_relationship("StaffRole", back_populates="staff")


class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True, index=True)
    street_line_1 = Column(CITEXT, nullable=False)
    street_line_2 = Column(CITEXT, nullable=False, server_default='') 
    city = Column(CITEXT, nullable=False)
    state_province = Column(CITEXT, nullable=False)
    postal_code = Column(CITEXT, nullable=False)
    country = Column(CITEXT, server_default='USA') # Use server_default here too
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('street_line_1', 'street_line_2', 'city', 'state_province', 'postal_code', 'country', name='uq_addresses_full'),
    )


class LocationType(Base):
    __tablename__ = "location_type"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)


class ProgramLocation(Base):
    __tablename__ = "program_locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    location_type_id = Column(Integer, ForeignKey("location_type.id"), nullable=False)
    location_type = sa_relationship("LocationType")
    group_number = Column(Integer)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# =============================================
# CLIENTS
# =============================================

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(CITEXT, nullable=False)
    middle_name = Column(CITEXT)
    last_name = Column(CITEXT, nullable=False)
    preferred_name = Column(CITEXT)
    suffix = Column(CITEXT)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(50))
    race = Column(String(100))
    height_feet = Column(Integer)
    height_inches = Column(Numeric(3, 1))
    medical_conditions = Column(Text)
    mobility_status = Column(String(100))
    profile_image_path = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('first_name', 'last_name', 'date_of_birth', name='uq_clients_name_dob'),
    )

    program_enrollments = sa_relationship("ClientProgramEnrollment", back_populates="client")


class RelationshipType(Base):
    __tablename__ = "relationship_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)


class ClientContact(Base):
    __tablename__ = "client_contacts"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    contact_first_name = Column(CITEXT, nullable=False)
    contact_middle_name = Column(CITEXT)
    contact_last_name = Column(CITEXT, nullable=False)
    contact_suffix_name = Column(CITEXT)
    contact_phone_primary = Column(String(20), nullable=False)
    contact_phone_secondary = Column(String(20))
    relationship = Column(Integer, ForeignKey("relationship_types.id"))
    is_primary = Column(Boolean, default=False)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="SET NULL"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint('client_id', 'contact_first_name', 'contact_last_name', 'contact_phone_primary', 'relationship', name='uq_client_contact_unique'),
    )
    
    address = sa_relationship("Address")


class ClientResidenceType(Base):
    __tablename__ = "client_residence_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)


class ClientResidenceHistory(Base):
    """Tracks client residence history. end_date=NULL means current residence."""
    __tablename__ = "client_residence_history"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    residence_type_id = Column(Integer, ForeignKey("client_residence_types.id", ondelete="RESTRICT"))
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="RESTRICT"))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)  # NULL = current residence
    end_status = Column(String(50)) # 'completed', 'cancelled'
    created_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))  # HIPAA audit
    ended_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))    # HIPAA audit
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime)  # HIPAA audit: exact time when ended
    __table_args__ = (
        UniqueConstraint('client_id', 'start_date', name='uq_residence_client_start'),
    )
    
    address = sa_relationship("Address")
    residence_type = sa_relationship("ClientResidenceType")


class ClientProgramEnrollment(Base):
    """Tracks client program enrollments. end_date=NULL means currently enrolled."""
    __tablename__ = "client_program_enrollments"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    program_location_id = Column(Integer, ForeignKey("program_locations.id", ondelete="RESTRICT"), nullable=False)
    start_date = Column(Date, server_default=text('CURRENT_DATE'), nullable=False)
    end_date = Column(Date)  # NULL = currently enrolled
    end_status = Column(String(50)) # 'completed', 'cancelled'
    created_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))  # HIPAA audit
    ended_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))    # HIPAA audit
    created_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime)  # HIPAA audit: exact time when ended
    # CheckConstraint removed to allow cancellation (end_date < start_date)

    client = sa_relationship("Client", back_populates="program_enrollments")


# =============================================
# TASKS & SHIFTS
# =============================================

class TaskCategory(Base):
    __tablename__ = "task_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, nullable=False)
    description = Column(Text)
    category_id = Column(Integer, ForeignKey("task_categories.id"))
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="SET NULL"))  # NULL = global, set = client-specific
    estimated_duration_minutes = Column(Integer)
    is_custom = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    __table_args__ = (
        Index('uq_tasks_template_name', 'category_id', 'name', unique=True, postgresql_where=text("is_custom = FALSE")),
    )


class TaskStatusType(Base):
    __tablename__ = "task_status_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, unique=True, nullable=False)


class ShiftTemplate(Base):
    __tablename__ = "shift_templates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    start_day_of_week = Column(Integer)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    program_location_id = Column(Integer, ForeignKey("program_locations.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("staff.id"))  # HIPAA audit trail
    # HIPAA: Soft-delete (archive) instead of hard-delete
    archived_at = Column(DateTime)  # NULL if active, timestamp when archived
    archived_by = Column(Integer, ForeignKey("staff.id"))  # Who archived this template
    is_overnight = Column(Boolean, default=False)
    __table_args__ = (
        CheckConstraint('start_day_of_week >= 0 AND start_day_of_week <= 6', name='chk_shift_template_day'),
        # Unique constraint is now a partial index in the database (only for non-archived templates)
    )
    shift_positions = sa_relationship("ShiftPosition", back_populates="template", cascade="all, delete-orphan", 
                                       primaryjoin="and_(ShiftTemplate.id==ShiftPosition.shift_template_id, ShiftPosition.is_active==True)",
                                       lazy="selectin")


class ShiftPosition(Base):
    __tablename__ = "shift_positions"
    id = Column(Integer, primary_key=True, index=True)
    shift_template_id = Column(Integer, ForeignKey("shift_templates.id", ondelete="CASCADE"), nullable=False)
    position_name = Column(CITEXT, nullable=False)
    description = Column(String(1024))
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("staff.id"))
    archived_at = Column(DateTime(timezone=True))
    archived_by = Column(Integer, ForeignKey("staff.id"))
    __table_args__ = (
        # Partial unique index defined in schema.sql: only active positions must be unique
    )
    template = sa_relationship("ShiftTemplate", back_populates="shift_positions")
    tasks = sa_relationship("ShiftPositionTask", back_populates="position", cascade="all, delete-orphan",
                           primaryjoin="and_(ShiftPosition.id==ShiftPositionTask.shift_position_id, ShiftPositionTask.is_active==True)",
                           lazy="selectin")
    clients = sa_relationship("ShiftPositionClient", back_populates="position", cascade="all, delete-orphan")
    created_by_user = sa_relationship("Staff", foreign_keys=[created_by])
    archived_by_user = sa_relationship("Staff", foreign_keys=[archived_by])


class ShiftPositionTask(Base):
    __tablename__ = "shift_position_tasks"
    id = Column(Integer, primary_key=True, index=True)
    shift_position_id = Column(Integer, ForeignKey("shift_positions.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    scheduled_start_time = Column(Time)
    scheduled_end_time = Column(Time)
    
    # HIPAA audit trail
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("staff.id"))
    archived_at = Column(DateTime)
    archived_by = Column(Integer, ForeignKey("staff.id"))
    
    __table_args__ = (
        # Removed UniqueConstraint - now a partial index in database (only for active tasks)
    )
    position = sa_relationship("ShiftPosition", back_populates="tasks")
    task = sa_relationship("Task")
    created_by_user = sa_relationship("Staff", foreign_keys=[created_by])
    archived_by_user = sa_relationship("Staff", foreign_keys=[archived_by])


class ShiftPositionClient(Base):
    __tablename__ = "shift_position_clients"
    id = Column(Integer, primary_key=True, index=True)
    shift_position_id = Column(Integer, ForeignKey("shift_positions.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    __table_args__ = (
        UniqueConstraint('shift_position_id', 'client_id', name='uq_position_client_unique'),
    )
    position = sa_relationship("ShiftPosition", back_populates="clients")
    client = sa_relationship("Client")


class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, index=True)
    shift_template_id = Column(Integer, ForeignKey("shift_templates.id"))
    program_location_id = Column(Integer, ForeignKey("program_locations.id"))
    start_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_date = Column(Date, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # HIPAA audit trail: Creation
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("staff.id"))
    
    # HIPAA audit trail: Cancellation (soft-delete)
    cancelled_at = Column(DateTime)           # NULL = active, has value = cancelled
    cancelled_by = Column(Integer, ForeignKey("staff.id"))
    
    __table_args__ = (
        UniqueConstraint('program_location_id', 'start_date', 'start_time', name='uq_shift_location_start'),
        CheckConstraint("(end_date = start_date AND end_time > start_time) OR (end_date = start_date + INTERVAL '1 day' AND end_time <= start_time)", name='chk_shift_dates_logic'),
    )


class ShiftEndStatusType(Base):
    """Lookup table for shift end status types (completed, timeout, etc.)"""
    __tablename__ = "shift_end_status_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, unique=True, nullable=False)
    description = Column(Text)


class ShiftAssignment(Base):
    __tablename__ = "shift_assignments"
    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="RESTRICT"), nullable=False)
    shift_position_id = Column(Integer, ForeignKey("shift_positions.id"), nullable=False)
    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(Integer, ForeignKey("staff.id"))  # HIPAA audit trail
    ended_at = Column(DateTime)
    ended_by = Column(Integer, ForeignKey("staff.id"))     # HIPAA audit trail
    end_status_id = Column(Integer, ForeignKey("shift_end_status_types.id"), nullable=False, default=4)
    # Note: Unique constraints are partial indexes in schema.sql (only for pending assignments)


class ShiftTaskStatus(Base):
    __tablename__ = "shift_task_status"
    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False)
    shift_position_id = Column(Integer, ForeignKey("shift_positions.id", ondelete="RESTRICT"), nullable=False)
    status_id = Column(Integer, ForeignKey("task_status_types.id"), default=1)
    scheduled_start_time = Column(Time)
    scheduled_end_time = Column(Time)
    completed_by_staff_id = Column(Integer, ForeignKey("staff.id"))
    completed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    __table_args__ = (
        UniqueConstraint('shift_id', 'shift_position_id', 'task_id', name='uq_shift_position_task_unique'),
    )


class ShiftTaskStatusHistory(Base):
    __tablename__ = "shift_task_status_history"
    id = Column(Integer, primary_key=True, index=True)
    shift_task_status_id = Column(Integer, ForeignKey("shift_task_status.id", ondelete="RESTRICT"), nullable=False)
    from_status_id = Column(Integer, ForeignKey("task_status_types.id"))
    to_status_id = Column(Integer, ForeignKey("task_status_types.id"), nullable=False)
    changed_by = Column(Integer, ForeignKey("staff.id", ondelete="RESTRICT"))  # NULL = system-initiated
    changed_at = Column(DateTime, server_default=func.now(), nullable=False)
    notes = Column(Text)
    completed_by_staff_id = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))


class LogCategory(Base):
    __tablename__ = "log_categories"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(CITEXT, unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text)
    display_order = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    icon = Column(String(50), default='folder')
    form_schema = Column(JSONB)


class ShiftDailyLog(Base):
    __tablename__ = "shift_daily_logs"
    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="RESTRICT"))
    staff_id = Column(Integer, ForeignKey("staff.id"))
    category_id = Column(Integer, ForeignKey("log_categories.id"))
    payload = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class StaffLogReadStatus(Base):
    __tablename__ = "staff_log_read_status"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"))
    log_shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="CASCADE"))
    read_during_shift_id = Column(Integer, ForeignKey("shifts.id", ondelete="CASCADE"))
    read_timestamp = Column(DateTime)
    __table_args__ = (
        UniqueConstraint('staff_id', 'log_shift_id', name='uq_staff_log_read_once'),
    )


# =============================================
# BEHAVIOR TRACKING
# =============================================

class BehaviorType(Base):
    __tablename__ = "behavior_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)


class ClientBehaviorConfigVersion(Base):
    """Master config version - one record per version, contains a set of behaviors"""
    __tablename__ = "client_behavior_config_versions"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"))
    version = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    notes = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('client_id', 'version', name='uq_client_version'),
        Index('uq_client_one_active_config', 'client_id', unique=True, postgresql_where=text('is_active = true')),
    )
    
    items = sa_relationship("ClientBehaviorConfigItem", back_populates="config_version", cascade="all, delete-orphan")
    client = sa_relationship("Client")
    creator = sa_relationship("Staff")


class ClientBehaviorConfigItem(Base):
    """Behaviors in each config version (many items per version)"""
    __tablename__ = "client_behavior_config_items"
    id = Column(Integer, primary_key=True, index=True)
    config_version_id = Column(Integer, ForeignKey("client_behavior_config_versions.id", ondelete="CASCADE"))
    behavior_type_id = Column(Integer, ForeignKey("behavior_types.id"))
    target_value = Column(Integer)
    notes = Column(Text)
    
    config_version = sa_relationship("ClientBehaviorConfigVersion", back_populates="items")
    behavior_type = sa_relationship("BehaviorType")


class BehaviorTrackingRecord(Base):
    __tablename__ = "behavior_tracking_records"
    id = Column(Integer, primary_key=True, index=True)
    shift_id = Column(Integer, ForeignKey("shifts.id"))
    staff_id = Column(Integer, ForeignKey("staff.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))
    behavior_type_id = Column(Integer, ForeignKey("behavior_types.id"))
    config_version_id = Column(Integer, ForeignKey("client_behavior_config_versions.id"), nullable=True)
    recorded_value = Column(Integer, nullable=False)
    recorded_at = Column(DateTime, server_default=func.now())
    notes = Column(Text)
    is_active = Column(Boolean, default=True)

    behavior_type = sa_relationship("BehaviorType")
    staff = sa_relationship("Staff")
    client = sa_relationship("Client")
    shift = sa_relationship("Shift")
    config_version = sa_relationship("ClientBehaviorConfigVersion")





# =============================================
# DOCUMENTS & COMMUNICATION
# =============================================

class DocumentCategory(Base):
    __tablename__ = "document_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(CITEXT, unique=True, nullable=False)
    description = Column(Text)
    icon = Column(String(50))
    is_active = Column(Boolean, default=True)





class ClientUpdate(Base):
    __tablename__ = "client_updates"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"))
    created_by = Column(Integer, ForeignKey("staff.id"))
    content = Column(Text, nullable=False)
    is_archived = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ClientUpdateRead(Base):
    __tablename__ = "client_update_reads"
    id = Column(Integer, primary_key=True, index=True)
    update_id = Column(Integer, ForeignKey("client_updates.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    read_at = Column(DateTime, server_default=func.now())


class DocumentSubcategory(Base):
    __tablename__ = "document_subcategories"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("document_categories.id"), nullable=False)
    name = Column(String(255), nullable=False)
    icon = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class DocumentTemplate(Base):
    __tablename__ = "document_templates"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("document_categories.id"))
    subcategory_id = Column(Integer, ForeignKey("document_subcategories.id"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    icon = Column(String(50), default="doc.text")
    version = Column(Integer, default=1)
    revision_interval_days = Column(Integer, default=365)
    form_schema = Column(JSONB, nullable=False)
    is_archived = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("staff.id"))
    created_at = Column(DateTime, server_default=func.now())


class ClientDocument(Base):
    __tablename__ = "client_documents"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    template_id = Column(Integer, ForeignKey("document_templates.id"), nullable=False)
    values = Column(JSONB, nullable=False)
    revision_notes = Column(Text)
    created_by = Column(Integer, ForeignKey("staff.id"))
    created_at = Column(DateTime, server_default=func.now())
    is_current = Column(Boolean, default=True)


class ClientDocumentAuditLog(Base):
    __tablename__ = "client_document_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("client_documents.id", ondelete="RESTRICT"), nullable=False)
    resulting_document_id = Column(Integer, ForeignKey("client_documents.id"))
    performed_by = Column(Integer, ForeignKey("staff.id"), nullable=False)
    performed_at = Column(DateTime, server_default=func.now())
    changes_made = Column(Boolean, default=False)
    action_type = Column(String(50))  # 'creation', 'edit', 'review', 'new_template', 'archived'
    notes = Column(Text)


class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    room_type = Column(String(50), default='group')
    program_location_id = Column(Integer, ForeignKey("program_locations.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"))
    sender_id = Column(Integer, ForeignKey("staff.id"))
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default='text')
    file_path = Column(String(500))
    is_edited = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class TrainingModule(Base):
    __tablename__ = "training_modules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    content = Column(Text)
    required_yearly = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class StaffTrainingRecord(Base):
    __tablename__ = "staff_training_records"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="RESTRICT"))
    training_module_id = Column(Integer, ForeignKey("training_modules.id"))
    completed_at = Column(DateTime)
    expires_at = Column(DateTime)
    notes = Column(Text)
    __table_args__ = (
        UniqueConstraint('staff_id', 'training_module_id', 'completed_at', name='uq_staff_training_unique'),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer)
    action = Column(String(50), nullable=False)
    old_values = Column(JSONB)
    new_values = Column(JSONB)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    ip_address = Column(String)
    user_agent = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class EncryptionKey(Base):
    __tablename__ = "encryption_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_name = Column(String(100), unique=True, nullable=False)
    encrypted_key = Column(Text, nullable=False)
    key_version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    is_active = Column(Boolean, default=True)


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False)
    severity = Column(String(20))
    description = Column(Text, nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    ip_address = Column(String)
    user_agent = Column(Text)
    additional_data = Column(JSONB)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class PermissionType(Base):
    __tablename__ = "permission_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)


class StaffPermission(Base):
    __tablename__ = "staff_permissions"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    permission_type_id = Column(Integer, ForeignKey("permission_types.id"))
    resource_type = Column(String(100))
    resource_id = Column(Integer)
    granted_by = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"))
    granted_at = Column(DateTime)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    session_token_hash = Column(Text, unique=True, nullable=False)
    ip_address = Column(String)
    user_agent = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    last_activity = Column(DateTime)
    is_active = Column(Boolean, default=True)

