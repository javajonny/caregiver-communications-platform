import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ConfirmationModal } from './ConfirmationModal';

interface Staff {
    id: number;
    first_name: string;
    last_name: string;
    role_name: string;
    assigned_location_id: number | null;
    is_active: boolean;
}

interface ShiftPosition {
    id: number;
    position_name: string;
    description: string;
}

interface Assignment {
    id: number;
    staff_id: number;
    shift_position_id: number;
    end_status_id: number | null;
    ended_at: string | null;
}

interface ShiftAssignmentsProps {
    shiftId: number;
    shiftTemplateId: number | null;
    onClose?: () => void;
    inline?: boolean;
    isReadOnly?: boolean;
}

interface TaskStatus {
    id: number;
    task_id: number;
    shift_position_id: number;
    status_id: number;
    notes: string | null;
    task_name: string | null;
}

interface DailyLog {
    id: number;
    shift_id: number;
    staff_id: number;
    category_id: number;
    category_name: string | null;
    payload: Record<string, unknown>;
    staff_name: string | null;
    created_at: string | null;
}

const END_STATUS_LABELS: Record<number, string> = {
    1: '✅ Completed',
    2: '⏰ Timed Out',
    3: '⚠️ Completed Late',
    4: '⏳ Pending'
};

const TASK_STATUS_LABELS: Record<number, string> = {
    1: 'Pending',
    2: 'Completed',
    4: 'Deleted',
    5: 'Not Completed',
    6: 'Incomplete (Explained)'
};

export function ShiftAssignments({ shiftId, shiftTemplateId, onClose, inline, isReadOnly }: ShiftAssignmentsProps) {
    const [positions, setPositions] = useState<ShiftPosition[]>([]);
    const [assignments, setAssignments] = useState<Assignment[]>([]);
    const [staff, setStaff] = useState<Staff[]>([]);
    const [taskStatuses, setTaskStatuses] = useState<TaskStatus[]>([]);
    const [dailyLogs, setDailyLogs] = useState<DailyLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const [confirmation, setConfirmation] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        variant: 'danger' | 'primary' | 'warning';
        action: () => void;
    }>({
        isOpen: false,
        title: '',
        message: '',
        variant: 'primary',
        action: () => { }
    });

    // Track selection state for adding assignments
    const [selectedStaff, setSelectedStaff] = useState<Record<number, string>>({}); // positionId -> staffId

    useEffect(() => {
        loadData();
    }, [shiftId, shiftTemplateId]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [assignmentsData, availableStaffData, taskStatusData, logsData] = await Promise.all([
                api.getShiftAssignments(shiftId),
                api.getAvailableStaffForShift(shiftId),  // Only get staff available for this shift
                api.getShiftTaskStatuses(shiftId),
                api.getShiftLogs(shiftId)
            ]);

            setAssignments(assignmentsData);
            setStaff(availableStaffData);  // This is now pre-filtered for availability
            setTaskStatuses(taskStatusData);
            setDailyLogs(logsData);

            if (shiftTemplateId) {
                const template = await api.getShiftTemplate(shiftTemplateId);
                // Schema now includes shift_positions
                setPositions(template.shift_positions || []);
            }
        } catch (err) {
            console.error(err);
            setError('Failed to load assignments');
        } finally {
            setLoading(false);
        }
    };

    const handleAssign = async (positionId: number) => {
        const staffId = Number(selectedStaff[positionId]);
        if (!staffId) return;

        try {
            await api.createShiftAssignment(shiftId, {
                shift_id: shiftId,
                staff_id: staffId,
                shift_position_id: positionId
            });
            await loadData(); // Reload to refresh list
            setSelectedStaff(prev => ({ ...prev, [positionId]: '' })); // Reset selection
        } catch (err: any) {
            const errorMsg = err?.response?.data?.detail || err?.message || 'Failed to assign staff';
            alert(errorMsg);
        }
    };

    const handleUnassign = (assignmentId: number) => {
        setConfirmation({
            isOpen: true,
            title: 'Remove Assignment',
            message: 'Are you sure you want to remove this staff assignment?',
            variant: 'danger',
            action: async () => {
                try {
                    await api.deleteShiftAssignment(assignmentId);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    await loadData();
                } catch (err) {
                    alert('Failed to remove assignment');
                }
            }
        });
    };

    // Staff is pre-filtered by backend (excludes overlapping shifts)
    // Just need to also exclude staff already assigned to THIS shift
    const getAvailableStaff = () => {
        const assignedStaffIds = assignments
            .filter(a => a.end_status_id === 4)  // Only pending assignments
            .map(a => a.staff_id);
        return staff.filter(s => !assignedStaffIds.includes(s.id));
    };

    const getAssignmentForPosition = (positionId: number) => {
        // Only return pending assignments (not cancelled)
        return assignments.find(a => a.shift_position_id === positionId && a.end_status_id === 4);
    };

    const getStaffName = (staffId: number) => {
        const s = staff.find(st => st.id === staffId);
        return s ? `${s.first_name} ${s.last_name}` : 'Unknown';
    };

    const content = (
        <div className={inline ? "assignments-inline" : "modal"} onClick={e => !inline && e.stopPropagation()} style={inline ? { padding: '10px 0' } : {}}>
            {!inline && <h2>Manage Assignments</h2>}

            {error && <div className="error-message">{error}</div>}

            {!shiftTemplateId && (
                <div className="alert-warning">
                    Custom shifts do not have predefined positions.
                    Assignments cannot be managed for this shift type yet.
                </div>
            )}

            {loading ? <p>Loading...</p> : (
                <div className="assignments-list">
                    {positions.length === 0 && shiftTemplateId && <p>No positions defined for this template.</p>}

                    {positions.map(position => {
                        const assignment = getAssignmentForPosition(position.id);
                        const availableStaff = getAvailableStaff();
                        const positionTaskStatuses = taskStatuses.filter(ts => ts.shift_position_id === position.id);

                        return (
                            <div key={position.id} className="assignment-row" style={inline ? { display: 'flex', flexDirection: 'column', padding: '12px 0', borderBottom: '1px solid #eee', gap: '8px' } : {}}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <div className="position-info">
                                        <div style={{ fontWeight: '500' }}>{position.position_name}</div>
                                        <small style={{ color: '#666' }}>{position.description}</small>
                                    </div>

                                    <div className="assignment-action">
                                        {assignment ? (
                                            <div className="assigned-user" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <span>{getStaffName(assignment.staff_id)}</span>
                                                {isReadOnly && assignment.end_status_id && (
                                                    <span style={{
                                                        fontSize: '12px',
                                                        padding: '2px 8px',
                                                        borderRadius: '12px',
                                                        background: assignment.end_status_id === 1 ? '#d4edda' :
                                                            assignment.end_status_id === 2 ? '#f8d7da' : '#fff3cd',
                                                        color: assignment.end_status_id === 1 ? '#155724' :
                                                            assignment.end_status_id === 2 ? '#721c24' : '#856404'
                                                    }}>
                                                        {END_STATUS_LABELS[assignment.end_status_id] || 'Unknown'}
                                                    </span>
                                                )}
                                                {!isReadOnly && (
                                                    <button
                                                        className="btn-icon"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            handleUnassign(assignment.id);
                                                        }}
                                                        title="Remove assignment"
                                                        style={{ color: '#dc3545', border: 'none', background: 'none', cursor: 'pointer', padding: '4px' }}
                                                    >
                                                        ✕
                                                    </button>
                                                )}
                                            </div>
                                        ) : (
                                            !isReadOnly && (
                                                <div className="assign-form" style={{ display: 'flex', gap: '8px' }}>
                                                    <select
                                                        value={selectedStaff[position.id] || ''}
                                                        onChange={e => setSelectedStaff(prev => ({
                                                            ...prev,
                                                            [position.id]: e.target.value
                                                        }))}
                                                        style={{ padding: '4px', borderRadius: '4px', border: '1px solid #ddd' }}
                                                    >
                                                        <option value="">Select Staff...</option>
                                                        {availableStaff.map(s => (
                                                            <option key={s.id} value={s.id}>
                                                                {s.first_name} {s.last_name} ({s.role_name})
                                                            </option>
                                                        ))}
                                                    </select>
                                                    <button
                                                        className="btn-sm"
                                                        disabled={!selectedStaff[position.id]}
                                                        onClick={() => handleAssign(position.id)}
                                                    >
                                                        Assign
                                                    </button>
                                                </div>
                                            )
                                        )}
                                    </div>
                                </div>
                                {/* Task Statuses for all shifts */}
                                {positionTaskStatuses.length > 0 && (
                                    <div style={{ marginLeft: '10px', marginTop: '4px' }}>
                                        <small style={{ color: '#888', fontWeight: '500' }}>Tasks:</small>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                                            {positionTaskStatuses.map(ts => (
                                                <span
                                                    key={ts.id}
                                                    title={ts.status_id === 6 && ts.notes ? `Explanation: ${ts.notes}` : undefined}
                                                    style={{
                                                        fontSize: '11px',
                                                        padding: '2px 6px',
                                                        borderRadius: '4px',
                                                        cursor: ts.status_id === 6 && ts.notes ? 'help' : 'default',
                                                        background: ts.status_id === 2 ? '#d4edda' :  // completed
                                                            ts.status_id === 5 ? '#f8d7da' :          // not_completed
                                                                ts.status_id === 6 ? '#ffe0b2' :          // incomplete_explained (orange)
                                                                    ts.status_id === 4 ? '#e2e3e5' :          // deleted (gray)
                                                                        '#fff3cd',                                // pending
                                                        color: ts.status_id === 2 ? '#155724' :
                                                            ts.status_id === 5 ? '#721c24' :
                                                                ts.status_id === 6 ? '#e65100' :
                                                                    ts.status_id === 4 ? '#383d41' :
                                                                        '#856404'
                                                    }}>
                                                    {ts.task_name || 'Unknown Task'}: {TASK_STATUS_LABELS[ts.status_id] || 'Unknown'}
                                                    {ts.status_id === 6 && ts.notes && ' ℹ️'}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Daily Logs Section */}
            {dailyLogs.length > 0 && (
                <div style={{ marginTop: '20px', borderTop: '1px solid #eee', paddingTop: '15px' }}>
                    <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#333' }}>Daily Log Notes</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {dailyLogs.map(log => (
                            <div key={log.id} style={{
                                background: '#f8f9fa',
                                padding: '12px',
                                borderRadius: '6px',
                                fontSize: '13px'
                            }}>
                                {/* Category Header */}
                                {log.category_name && (
                                    <div style={{
                                        fontWeight: '600',
                                        color: '#2c3e50',
                                        marginBottom: '6px',
                                        fontSize: '13px'
                                    }}>
                                        {log.category_name}
                                    </div>
                                )}
                                {/* Log content */}
                                <div style={{ color: '#212529', marginBottom: '6px' }}>
                                    {Object.entries(log.payload || {}).map(([key, value]) => {
                                        // Convert snake_case to Title Case (matching app behavior)
                                        const formattedKey = key
                                            .replace(/_/g, ' ')
                                            .replace(/\b\w/g, c => c.toUpperCase());
                                        return (
                                            <div key={key}>
                                                <span style={{ color: '#6c757d' }}>{formattedKey}: </span>
                                                {typeof value === 'string' ? value : JSON.stringify(value)}
                                            </div>
                                        );
                                    })}
                                </div>
                                {/* Staff and timestamp */}
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#6c757d' }}>
                                    <span>{log.staff_name || 'Unknown Staff'}</span>
                                    <span>
                                        {log.created_at ? new Date(log.created_at).toLocaleString() : ''}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {!inline && (
                <div className="form-actions">
                    <button className="btn-secondary" onClick={onClose}>Close</button>
                </div>
            )}
        </div>
    );

    if (inline) {
        return (
            <div className="shift-assignments-container-inline">
                {content}
                <ConfirmationModal
                    isOpen={confirmation.isOpen}
                    title={confirmation.title}
                    message={confirmation.message}
                    variant={confirmation.variant}
                    confirmText={confirmation.variant === 'danger' ? 'Delete' : 'Confirm'}
                    onConfirm={confirmation.action}
                    onCancel={() => setConfirmation(prev => ({ ...prev, isOpen: false }))}
                />
            </div>
        );
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            {content}
            <ConfirmationModal
                isOpen={confirmation.isOpen}
                title={confirmation.title}
                message={confirmation.message}
                variant={confirmation.variant}
                confirmText={confirmation.variant === 'danger' ? 'Delete' : 'Confirm'}
                onConfirm={confirmation.action}
                onCancel={() => setConfirmation(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
}
