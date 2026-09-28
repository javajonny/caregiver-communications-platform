-- =============================================
-- EXTENSIONS
-- =============================================
CREATE EXTENSION IF NOT EXISTS citext;

-- =============================================
-- STAFF AND SECURITY MANAGEMENT (HIPAA)
-- =============================================
CREATE TABLE staff_roles (
    id SERIAL PRIMARY KEY,
    role_name CITEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    street_line_1 CITEXT NOT NULL,
    street_line_2 CITEXT NOT NULL DEFAULT '',
    city CITEXT NOT NULL,
    state_province CITEXT NOT NULL,
    postal_code CITEXT NOT NULL,    
    country CITEXT DEFAULT 'USA',        
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (street_line_1, street_line_2, city, state_province, postal_code, country)
);

CREATE TABLE location_type (
    id SERIAL PRIMARY KEY,
    name CITEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Allow duplicate names if one is inactive (HIPAA audit trail)
CREATE UNIQUE INDEX uq_location_type_active_name 
ON location_type (name) 
WHERE is_active = true;

CREATE TABLE program_locations (
    id SERIAL PRIMARY KEY,
    name CITEXT NOT NULL,
    location_type_id INTEGER REFERENCES location_type(id) NOT NULL,          
    group_number INTEGER,
    address_id INTEGER REFERENCES addresses(id) ON DELETE RESTRICT NOT NULL, 
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unfortunately, we can't directly reference another table (like location_type.name) inside a WHERE clause of a CREATE INDEX statement in PostgreSQL --> location type IDs are hardcoded (1 = residential, 2 = dayhab)
-- Case-insensitive uniqueness for Residential locations
CREATE UNIQUE INDEX uq_program_location_residential
ON program_locations (location_type_id, address_id)
WHERE location_type_id = 1;

-- Case-insensitive uniqueness for Dayhab locations (group number required)
CREATE UNIQUE INDEX uq_program_location_dayhab
ON program_locations (location_type_id, group_number, address_id)
WHERE location_type_id = 2;

CREATE TABLE staff (
    id SERIAL PRIMARY KEY,
    first_name CITEXT NOT NULL,
    middle_name CITEXT,
    last_name CITEXT NOT NULL,
    preferred_name CITEXT,
    suffix CITEXT,
    work_email CITEXT UNIQUE NOT NULL,
    work_phone VARCHAR(20),
    password_hash VARCHAR(255) NOT NULL,
    must_change_password BOOLEAN DEFAULT true,
    role_id INTEGER REFERENCES staff_roles(id) NOT NULL,
    assigned_location_id INTEGER REFERENCES program_locations(id),  -- NULL = all locations, set = scoped to location
    profile_image_path VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    failed_login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE clients (
    id SERIAL PRIMARY KEY,
    first_name CITEXT NOT NULL,
    middle_name CITEXT,
    last_name CITEXT NOT NULL,
    preferred_name CITEXT,
    suffix CITEXT,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(50), 
    race VARCHAR(100), 
    height_feet INTEGER, 
    height_inches DECIMAL(3, 1),
    medical_conditions TEXT,
    mobility_status VARCHAR(100),
    profile_image_path VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
    UNIQUE (first_name, last_name, date_of_birth)
);

CREATE TABLE relationship_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE client_contacts (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    contact_first_name CITEXT NOT NULL,
    contact_middle_name CITEXT,
    contact_last_name CITEXT NOT NULL,
    contact_suffix_name CITEXT,
    contact_phone_primary VARCHAR(20) NOT NULL,
    contact_phone_secondary VARCHAR(20),
    relationship INTEGER REFERENCES relationship_types(id),
    is_primary BOOLEAN DEFAULT FALSE,
    address_id INTEGER REFERENCES addresses(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(client_id, contact_first_name, contact_last_name, contact_phone_primary, relationship)
    
);

CREATE TABLE client_residence_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE client_residence_history (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE RESTRICT NOT NULL,
    residence_type_id INTEGER REFERENCES client_residence_types(id) ON DELETE RESTRICT,
    address_id INTEGER REFERENCES addresses(id) ON DELETE RESTRICT,
    start_date DATE NOT NULL,
    end_date DATE, -- NULL means current residence
    end_status VARCHAR(50), -- 'completed', 'cancelled'
    created_by INTEGER REFERENCES staff(id) ON DELETE SET NULL, -- HIPAA audit
    ended_by INTEGER REFERENCES staff(id) ON DELETE SET NULL,   -- HIPAA audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ended_at TIMESTAMP, -- HIPAA audit: exact time when ended
    CONSTRAINT uq_residence_client_start UNIQUE(client_id, start_date)
);

CREATE INDEX idx_residence_current ON client_residence_history (client_id) WHERE end_date IS NULL;

CREATE TABLE client_program_enrollments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE RESTRICT NOT NULL,
    program_location_id INTEGER REFERENCES program_locations(id) ON DELETE RESTRICT NOT NULL,
    start_date DATE DEFAULT CURRENT_DATE NOT NULL,
    end_date DATE, -- NULL means currently enrolled
    end_status VARCHAR(50), -- 'completed', 'cancelled'
    created_by INTEGER REFERENCES staff(id) ON DELETE SET NULL, -- HIPAA audit
    ended_by INTEGER REFERENCES staff(id) ON DELETE SET NULL,   -- HIPAA audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP -- HIPAA audit: exact time when ended
);

-- Only one active enrollment per client per location (allows re-enrollment after ending)
CREATE UNIQUE INDEX idx_enrollment_active 
ON client_program_enrollments (client_id, program_location_id) 
WHERE end_date IS NULL;

CREATE TABLE permission_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE staff_permissions (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE SET NULL,
    permission_type_id INTEGER REFERENCES permission_types(id),
    resource_type VARCHAR(100),
    resource_id INTEGER,
    granted_by INTEGER REFERENCES staff(id) ON DELETE SET NULL,
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE CASCADE,
    session_token_hash TEXT UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- =============================================
-- TASK MANAGEMENT (moved earlier for FK deps)
-- =============================================
CREATE TABLE task_categories (
    id SERIAL PRIMARY KEY,
    name CITEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    name CITEXT NOT NULL,
    description TEXT,
    category_id INTEGER NOT NULL REFERENCES task_categories(id),
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,  -- NULL = global task, set = client-specific
    estimated_duration_minutes INTEGER,
    is_custom BOOLEAN DEFAULT false,
    created_by INTEGER REFERENCES staff(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Only enforce uniqueness for template tasks (is_custom = FALSE)
-- Custom tasks can have duplicate names since they're shift-specific
CREATE UNIQUE INDEX uq_tasks_template_name 
ON tasks (category_id, name) 
WHERE is_custom = FALSE;

CREATE TABLE task_status_types (
    id SERIAL PRIMARY KEY,
    name CITEXT UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- =============================================
-- SHIFT MANAGEMENT
-- =============================================
CREATE TABLE shift_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    start_day_of_week INTEGER CHECK (start_day_of_week >= 0 AND start_day_of_week <= 6), 
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    program_location_id INTEGER REFERENCES program_locations(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES staff(id),  -- HIPAA audit trail
    -- HIPAA: Soft-delete (archive) instead of hard-delete
    archived_at TIMESTAMP,  -- NULL if active, timestamp when archived
    archived_by INTEGER REFERENCES staff(id),  -- Who archived this template
    is_overnight BOOLEAN NOT NULL DEFAULT FALSE
    -- Uniqueness enforced via partial index below (only for non-archived templates)
);

-- Unique constraint only applies to non-archived templates
-- This allows re-creating a template with the same parameters after archiving
CREATE UNIQUE INDEX uq_shift_template_time_per_location_active
ON shift_templates (program_location_id, start_day_of_week, start_time, end_time)
WHERE archived_at IS NULL;

CREATE TABLE shift_positions (
    id SERIAL PRIMARY KEY,
    shift_template_id INTEGER NOT NULL REFERENCES shift_templates(id) ON DELETE CASCADE,
    position_name CITEXT NOT NULL,
    description VARCHAR(1024),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES staff(id),
    archived_at TIMESTAMP WITH TIME ZONE,
    archived_by INTEGER REFERENCES staff(id)
);

-- Partial unique index: only enforce uniqueness for active positions
CREATE UNIQUE INDEX uq_shift_position_name_per_template_active 
    ON shift_positions(shift_template_id, position_name) 
    WHERE is_active = TRUE;

CREATE INDEX idx_shift_positions_is_active ON shift_positions(is_active) WHERE is_active = TRUE;

CREATE TABLE shift_position_tasks (
    id SERIAL PRIMARY KEY,
    shift_position_id INTEGER NOT NULL REFERENCES shift_positions(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    scheduled_start_time TIME,
    scheduled_end_time TIME,
    -- HIPAA audit trail: soft-delete pattern
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES staff(id),
    archived_at TIMESTAMP,
    archived_by INTEGER REFERENCES staff(id)
);

-- Partial unique index: only active position tasks must be unique
CREATE UNIQUE INDEX uq_position_task_active ON shift_position_tasks(shift_position_id, task_id) WHERE is_active = TRUE;

COMMENT ON COLUMN shift_position_tasks.is_active IS 'Soft-delete flag: TRUE = active, FALSE = archived';
COMMENT ON COLUMN shift_position_tasks.archived_at IS 'HIPAA audit: when this position task was archived';
COMMENT ON COLUMN shift_position_tasks.archived_by IS 'HIPAA audit: which staff member archived this position task';
COMMENT ON COLUMN shift_position_tasks.created_by IS 'HIPAA audit: which staff member created this position task';

CREATE TABLE shift_position_clients (
    id SERIAL PRIMARY KEY,
    shift_position_id INTEGER NOT NULL REFERENCES shift_positions(id) ON DELETE CASCADE,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    UNIQUE(shift_position_id, client_id)
);

CREATE TABLE shifts (
    id SERIAL PRIMARY KEY,
    shift_template_id INTEGER REFERENCES shift_templates(id),
    program_location_id INTEGER REFERENCES program_locations(id),
    start_date DATE NOT NULL, 
    start_time TIME NOT NULL,
    end_date DATE NOT NULL, 
    end_time TIME NOT NULL,
    
    -- HIPAA audit trail: Creation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by INTEGER REFERENCES staff(id),
    
    -- HIPAA audit trail: Cancellation (soft-delete)
    cancelled_at TIMESTAMP,           -- NULL = active, has value = cancelled
    cancelled_by INTEGER REFERENCES staff(id),
    
    UNIQUE(program_location_id, start_date, start_time), 
    CONSTRAINT chk_shift_dates_logic CHECK (
        (end_date = start_date AND end_time > start_time) OR 
        (end_date = start_date + INTERVAL '1 day' AND end_time <= start_time)
    )
);

CREATE TABLE shift_end_status_types (
    id SERIAL PRIMARY KEY,
    name CITEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE
);
-- Values: completed, timeout, completed_late, pending, cancelled

CREATE TABLE shift_assignments (
    id SERIAL PRIMARY KEY,
    shift_id INTEGER NOT NULL REFERENCES shifts(id) ON DELETE RESTRICT,
    staff_id INTEGER NOT NULL REFERENCES staff(id) ON DELETE RESTRICT,
    shift_position_id INTEGER NOT NULL REFERENCES shift_positions(id), 
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INTEGER REFERENCES staff(id),  -- Who created this assignment
    ended_at TIMESTAMP,
    ended_by INTEGER REFERENCES staff(id),     -- Who ended/cancelled this assignment
    end_status_id INTEGER NOT NULL DEFAULT 4 REFERENCES shift_end_status_types(id)
);

-- Partial unique indexes: only enforce uniqueness for PENDING assignments (end_status_id = 4)
-- This allows reassigning positions after cancellation while preventing double-booking
CREATE UNIQUE INDEX uq_assignment_shift_staff_pending 
ON shift_assignments (shift_id, staff_id) 
WHERE end_status_id = 4;

CREATE UNIQUE INDEX uq_assignment_shift_position_pending 
ON shift_assignments (shift_id, shift_position_id) 
WHERE end_status_id = 4;


CREATE TABLE log_categories (
    id SERIAL PRIMARY KEY,
    key CITEXT UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    display_order INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    icon VARCHAR(50) DEFAULT 'folder',
    form_schema JSONB DEFAULT NULL
);

CREATE TABLE shift_daily_logs (
    id SERIAL PRIMARY KEY,
    shift_id INTEGER REFERENCES shifts(id) ON DELETE RESTRICT,
    staff_id INTEGER REFERENCES staff(id),
    category_id INTEGER REFERENCES log_categories(id),
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Tracks when a staff member reads a specific shift's log note. 
CREATE TABLE staff_log_read_status (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER REFERENCES staff(id) ON DELETE CASCADE, 
    log_shift_id INTEGER REFERENCES shifts(id) ON DELETE CASCADE, --  shift_id refers to the log note (shift) that was read
    read_during_shift_id INTEGER REFERENCES shifts(id) ON DELETE CASCADE, -- shift_id refers to the shift during which the log was read
    read_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(staff_id, log_shift_id)  --  ensures a staff member only needs to mark a shift's log as read once.
);


CREATE TABLE shift_task_status (
    id SERIAL PRIMARY KEY,
    shift_id INTEGER NOT NULL REFERENCES shifts(id) ON DELETE RESTRICT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
    shift_position_id INTEGER NOT NULL REFERENCES shift_positions(id) ON DELETE RESTRICT,
    status_id INTEGER REFERENCES task_status_types(id) DEFAULT 1,
    scheduled_start_time TIME,
    scheduled_end_time TIME,
    completed_by_staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL,
    completed_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(shift_id, shift_position_id, task_id)
);

-- =============================================
-- TASK STATUS AUDIT TRAIL (for HIPAA accountability)
-- =============================================
-- Tracks every status change for complete audit trail
CREATE TABLE shift_task_status_history (
    id SERIAL PRIMARY KEY,
    shift_task_status_id INTEGER NOT NULL REFERENCES shift_task_status(id) ON DELETE RESTRICT,
    from_status_id INTEGER REFERENCES task_status_types(id),
    to_status_id INTEGER NOT NULL REFERENCES task_status_types(id),
    changed_by INTEGER REFERENCES staff(id) ON DELETE RESTRICT,  -- NULL = system-initiated (e.g., timeout)
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    -- Track who marked it complete (useful for pending→completed transition)
    completed_by_staff_id INTEGER REFERENCES staff(id) ON DELETE SET NULL
);

-- =============================================
-- BEHAVIOR TRACKING
-- =============================================
CREATE TABLE behavior_types (
    id SERIAL PRIMARY KEY,
    name CITEXT UNIQUE NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true
);

-- Master config version (one record per version, contains a set of behaviors)
CREATE TABLE client_behavior_config_versions (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES staff(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    UNIQUE(client_id, version)
);
-- Only one active version per client
CREATE UNIQUE INDEX uq_client_one_active_config ON client_behavior_config_versions (client_id) WHERE is_active = true;

-- Behaviors in each config version (many items per version)
CREATE TABLE client_behavior_config_items (
    id SERIAL PRIMARY KEY,
    config_version_id INTEGER REFERENCES client_behavior_config_versions(id) ON DELETE CASCADE,
    behavior_type_id INTEGER REFERENCES behavior_types(id),
    target_value INTEGER,
    notes TEXT
);

CREATE TABLE behavior_tracking_records (
    id SERIAL PRIMARY KEY,
    shift_id INTEGER REFERENCES shifts(id),
    staff_id INTEGER REFERENCES staff(id),
    client_id INTEGER REFERENCES clients(id),
    behavior_type_id INTEGER REFERENCES behavior_types(id),
    config_version_id INTEGER REFERENCES client_behavior_config_versions(id),
    recorded_value INTEGER NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    is_active BOOLEAN DEFAULT true
);



-- =============================================
-- DOCUMENT MANAGEMENT
-- =============================================
CREATE TABLE document_categories (
    id SERIAL PRIMARY KEY,
    name CITEXT UNIQUE NOT NULL,
    description TEXT,
    icon VARCHAR(50),
    is_active BOOLEAN DEFAULT true
);



-- =============================================
-- COMMUNICATION AND UPDATES
-- =============================================
CREATE TABLE client_updates (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE RESTRICT,
    created_by INTEGER REFERENCES staff(id),
    content TEXT NOT NULL,
    is_archived BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tracks which staff have read which updates
CREATE TABLE client_update_reads (
    id SERIAL PRIMARY KEY,
    update_id INTEGER REFERENCES client_updates(id) ON DELETE CASCADE NOT NULL,
    staff_id INTEGER REFERENCES staff(id) ON DELETE CASCADE NOT NULL,
    read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(update_id, staff_id)
);

-- =============================================
-- CLIENT DOCUMENTS (Flexible Template System)
-- =============================================

-- Subcategories for organizing documents within categories
CREATE TABLE document_subcategories (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES document_categories(id) NOT NULL,
    name CITEXT NOT NULL,
    icon VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_id, name)
);

-- Document templates with JSONB form schema (versioned - create new row for updates)
CREATE TABLE document_templates (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES document_categories(id),
    subcategory_id INTEGER REFERENCES document_subcategories(id),  -- optional subcategory
    name VARCHAR(255) NOT NULL,
    description TEXT,
    icon VARCHAR(50) DEFAULT 'doc.text',
    version INTEGER DEFAULT 1,
    revision_interval_days INTEGER DEFAULT 365,  -- required review interval (e.g., 365 = yearly)
    form_schema JSONB NOT NULL,  -- defines sections & fields
    is_archived BOOLEAN DEFAULT false,
    created_by INTEGER REFERENCES staff(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category_id, name, version)  -- prevent duplicate versions
);

-- Client-specific document instances with filled values (multiple versions allowed)
CREATE TABLE client_documents (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE RESTRICT NOT NULL,
    template_id INTEGER REFERENCES document_templates(id) ON DELETE RESTRICT NOT NULL,
    values JSONB NOT NULL,  -- the filled-in data
    revision_notes TEXT,    -- optional notes about what changed
    created_by INTEGER REFERENCES staff(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT true
    -- No UNIQUE constraint: allows multiple versions per client/template
);

-- Document audit trail (tracks all document actions for HIPAA compliance)
CREATE TABLE client_document_audit_log (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES client_documents(id) ON DELETE RESTRICT NOT NULL,  -- document being actioned
    resulting_document_id INTEGER REFERENCES client_documents(id) ON DELETE RESTRICT,  -- new version created (NULL if no new version)
    performed_by INTEGER REFERENCES staff(id) ON DELETE SET NULL NOT NULL,  -- who performed the action
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changes_made BOOLEAN DEFAULT false,  -- true if action resulted in a new document version
    action_type VARCHAR(50), -- 'creation', 'edit', 'review', 'new_template', 'archived'
    notes TEXT
);

-- =============================================
-- TRAINING AND COMPLIANCE
-- =============================================
CREATE TABLE training_modules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    content TEXT,
    required_yearly BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE staff_training_records (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER REFERENCES staff(id) ON DELETE RESTRICT,
    training_module_id INTEGER REFERENCES training_modules(id),
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    notes TEXT,
    UNIQUE(staff_id, training_module_id, completed_at)
);

-- =============================================
-- AUDIT AND LOGGING
-- =============================================
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id INTEGER,
    action VARCHAR(50) NOT NULL, 
    old_values JSONB,
    new_values JSONB,
    staff_id INTEGER REFERENCES staff(id),
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE encryption_keys (
    id SERIAL PRIMARY KEY,
    key_name VARCHAR(100) UNIQUE NOT NULL,
    encrypted_key TEXT NOT NULL,
    key_version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE security_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20),
    description TEXT NOT NULL,
    staff_id INTEGER REFERENCES staff(id),
    ip_address INET,
    user_agent TEXT,
    additional_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
