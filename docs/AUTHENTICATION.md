# API Authentication Implementation Summary

## What Changed

All API endpoints now require authentication via bearer token. Unauthenticated requests will receive `401 Unauthorized`.


## Protected Endpoints

All API endpoints across the routers are protected:
- `/staff/**` - Staff management
- `/clients/**` - Client management
- `/shifts/**` - Shifts, tasks, logs
- `/locations/**` - Addresses, programs
- `/documents/**` - Document templates and client documents
- `/behavior-types/**`, `/behavior-tracking/**` - Behavior tracking

## Public Endpoints (no auth required)

Only the login endpoint remains public:
- `POST /auth/login`

## Implementation Details

### Router-Level Protection
Used FastAPI's `dependencies` parameter on routers for clean, centralized auth:

```python
router = APIRouter(
    prefix="/staff",
    tags=["Staff"],
    dependencies=[Depends(get_current_active_user)]  # <- All endpoints require auth
)
```

### Benefits
- Single line per router (vs. adding dependency to each endpoint)
- Impossible to forget protection on new endpoints
- Enforces session idle timeout and absolute TTL on every request
- Returns `401` with clear error messages for auth failures

## Testing Protected Endpoints

### With curl:
```bash
# 1. Login
TOKEN=$(curl -sk https://localhost:8443/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"daniel.davidson@aco.com","password":"XXXXXXXXX"}' \
  | jq -r '.access_token')

# 2. Access protected endpoint
curl -k https://localhost:8443/staff \
  -H "Authorization: Bearer $TOKEN"
```

### With Bruno/Postman:
1. POST `/auth/login` with email/password
2. Copy `access_token` from response
3. Add header to all requests: `Authorization: Bearer <token>`

## Session Management

- **Idle timeout**: 10 minutes (configurable via `SESSION_IDLE_TIMEOUT_MINUTES`)
- **Absolute TTL**: 12 hours (configurable via `SESSION_ABSOLUTE_TTL_MINUTES`)
- **Sliding window**: Each valid request extends the idle timeout
- **Server-side**: Tokens are hashed (SHA-256) and validated against database

## Role-Based Authorization (Implemented)

RBAC is fully implemented. See `docs/RBAC_PERMISSIONS.md` for the complete permissions matrix.

### Implementation Examples (from `server/authorization.py`):

### Example 1: Admin-only endpoint
```python
from authorization import require_role

@router.delete("/{staff_id}")
def deactivate_staff(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: Staff = Depends(require_roles(["admin"]))
):
# only admins can deactivate staff
...
```

### Example 2: Multiple roles allowed
```python
from authorization import require_roles

@router.post("/shift-templates")
def create_shift_template(
    data: ShiftTemplateCreate,
    user: Staff = Depends(require_roles(["admin", "manager"])),
    db: Session = Depends(get_db)
):
    # Only admins or managers can create shift templates
    ...
```

### Example 3: Resource-based (shift access)
```python
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
...
```

## Security Improvements

✅ No more anonymous access to sensitive data  
✅ HIPAA-compliant session management  
✅ Automatic session expiration (idle + absolute)  
✅ Server-side token validation  
✅ Bcrypt password hashing (no plaintext storage)  
✅ Role-based access control (RBAC) implemented

---

## iOS HTTPS Setup

For local HTTPS testing with iOS devices:

### 1. Generate self-signed certificate (one-time)

```bash
openssl req -x509 -newkey rsa:4096 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=localhost"
```

### 2. Run server with HTTPS

```bash
uvicorn main:app --host 0.0.0.0 --port 8443 --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

### 3. Trust certificate on iOS

1. Email yourself `cert.pem`
2. Install it on your device
3. Go to **Settings → General → About → Certificate Trust Settings**
4. Enable trust for the certificate
