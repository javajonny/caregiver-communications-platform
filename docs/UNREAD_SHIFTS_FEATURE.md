# Unread Shifts Feature

## Overview
This feature displays unread shift logs to staff members at login. It ensures staff members review all shift logs from previous shifts before starting their work, including shifts where they left early and missed updates.

## Implementation

### 1. Database (Already Exists)
- **Table**: `staff_log_read_status`
- **Purpose**: Tracks which shifts each staff member has marked as read
- **Columns**:
  - `staff_id`: References staff member
  - `log_shift_id`: The shift whose logs were read
  - `read_during_shift_id`: Optional - which shift they were working when they read it
  - `read_timestamp`: When they marked it as read

### 2. Backend API

#### New Endpoints in `/shifts`:

**GET `/shifts/unread`**
- Returns list of unread shifts for authenticated user
- A shift is "unread" if:
  - Shift has ended (past timestamp)
  - Shift has daily log entries
  - User has NOT marked it as read
  - Shift is at a location where the user works

**POST `/shifts/mark-read`**
- Marks a shift's logs as read
- Body: `{ "log_shift_id": int, "read_during_shift_id": int? }`

#### New Schemas (schemas.py):
```python
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
```

### 3. iOS App

#### New Files:

**Models/ShiftModels.swift**
- Added `UnreadShift` struct
- Added `MarkLogReadRequest` struct

**Services/ShiftService.swift**
- `fetchUnreadShifts(token:)` - Gets unread shifts
- `markShiftAsRead(token:logShiftId:readDuringShiftId:)` - Marks shift as read

**Shift/UnreadShiftsView.swift**
- Modal view displaying unread shifts
- Shows:
  - Program location name
  - Shift date/time
  - Number of log entries
  - Time elapsed since shift ended
- Features:
  - Mark individual shifts as read
  - Loading and error states
  - Integration with `ContentView.swift`: Uses `@State` to present as sheet after login

## User Flow

1. Staff member logs in
2. Main app loads (tabs visible)
3. **UnreadShiftsView modal appears** if there are unread shifts
4. Staff reviews each shift:
   - Sees program location, date, time
   - Sees number of log entries
   - Slides "Slide to Mark as Read" for each shift
5. When all shifts marked as read:
   - "All caught up!" message appears
   - View stays open until user dismisses it

## Why This Approach?
The staff must acknowledge also his last shift because he can leave early and miss log updates made during his shift.
### Problem Solved:
- Staff members can leave early and miss log updates made during their shift
- Staff need to stay informed about previous shifts at their location
- Ensures communication continuity across shifts

### Design Decisions:

1. **Modal at Login**: 
   - Forces acknowledgment

2. **Individual "Mark as Read"**:
   - Staff explicitly confirms reviewing each shift
   - Can't accidentally skip shifts

3. **Location-Based**:
   - Only shows shifts at locations where staff member works
   - Reduces noise from irrelevant shifts

## Testing

### Backend Testing:
```bash
# Get unread shifts
curl -H "Authorization: Bearer <token>" https://localhost:8443/shifts/unread

# Mark shift as read
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"log_shift_id": 7}' \
  https://localhost:8443/shifts/mark-read
```

### Manual Testing in iOS app:
1. Login as staff member (e.g., daniel.davidson@aco.com; password see `database/mock_data.txt`)
2. Should see modal with unread shifts (if any exist)
3. Mark shifts as read one by one
4. "All caught up!" message appears which can be dismissed
5. Re-login - should NOT see those shifts again - only the "All caught up" message