"""
HIPAA Audit Logging Service

Provides methods to log PHI access and security events to the database
for compliance with HIPAA Security Rule §164.312(b).
"""
from sqlalchemy.orm import Session
from models import AuditLog, SecurityEvent


class AuditService:
    """
    Service for logging audit events to the database.
    
    Usage:
        audit = AuditService(db, user_id=current_user.id, ip="1.2.3.4", user_agent="...")
        audit.log_data_access("read", "clients", client_id)
    """
    
    def __init__(
        self,
        db: Session,
        user_id: int = None,
        ip: str = None,
        user_agent: str = None
    ):
        self.db = db
        self.user_id = user_id
        self.ip = ip
        self.user_agent = user_agent

    def log_data_access(
        self,
        action: str,
        table_name: str,
        record_id: int,
        old_values: dict = None,
        new_values: dict = None
    ):
        """
        Log access to Protected Health Information (PHI).
        
        Args:
            action: 'create', 'read', 'update', or 'delete'
            table_name: Database table name (e.g., 'clients', 'client_documents')
            record_id: Primary key of the accessed record
            old_values: Previous values (for updates/deletes)
            new_values: New values (for creates/updates)
        """
        entry = AuditLog(
            table_name=table_name,
            record_id=record_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            staff_id=self.user_id,
            ip_address=self.ip,
            user_agent=self.user_agent
        )
        self.db.add(entry)
        # Note: Caller is responsible for committing the transaction

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        description: str,
        additional_data: dict = None
    ):
        """
        Log a security-related event.
        
        Args:
            event_type: Type of event (e.g., 'login_success', 'login_failure', 'logout',
                       'password_change', 'admin_password_reset', 'unauthorized_access')
            severity: 'info', 'warning', 'error', or 'critical'
            description: Human-readable description of the event
            additional_data: Optional JSON data for context
        """
        entry = SecurityEvent(
            event_type=event_type,
            severity=severity,
            description=description,
            staff_id=self.user_id,
            ip_address=self.ip,
            user_agent=self.user_agent,
            additional_data=additional_data
        )
        self.db.add(entry)
        # Note: Caller is responsible for committing the transaction
