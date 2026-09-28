import React, { useEffect, useState } from 'react';
import { ShiftTemplatesTab } from './ShiftTemplates';
import { api } from '../services/api';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { usePermission } from '../hooks/usePermission';
import { ShiftAssignments } from '../components/ShiftAssignments';

interface Shift {
    id: number;
    shift_template_id: number | null;
    program_location_id: number;
    start_date: string;
    start_time: string;
    end_date: string;
    end_time: string;
}

interface ShiftTemplate {
    id: number;
    name: string;
    program_location_id: number;
    start_day_of_week: number;
    start_time: string;
    end_time: string;
    is_active: boolean;
    shift_positions: ShiftPosition[];
}

interface Client {
    id: number;
    first_name: string;
    last_name: string;
}

interface ShiftPositionClient {
    client: Client;
}

interface ShiftPosition {
    id: number;
    position_name: string;
    clients: ShiftPositionClient[];
}

interface Staff {
    id: number;
    first_name: string;
    last_name: string;
    role_name?: string;
    assigned_location_id?: number | null;
    is_active: boolean;
}

interface Location {
    id: number;
    name: string;
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

// Shift times are stored in America/New_York timezone.
// This must match the TZ env var in docker-compose.yml / server config.
const SHIFT_TIMEZONE = 'America/New_York';

// DEV ONLY: Set to a date-time string (NY time) to fake the current time, or null to use real time.
// Must match FAKE_NOW in docker-compose.yml server environment.
const DEV_FAKE_NOW: string | null = '2026-03-30T10:00:00';

/** Returns "now" — either real or faked for dev/testing. */
function getNow(): Date {
    if (DEV_FAKE_NOW) {
        return toTZDate(DEV_FAKE_NOW.split('T')[0], DEV_FAKE_NOW.split('T')[1]);
    }
    return new Date();
}

/**
 * Convert a date + time string (in SHIFT_TIMEZONE) to a proper UTC-based Date object.
 * Without this, `new Date("2026-03-25T15:00:00")` would be parsed as local browser time
 * (e.g., 15:00 Berlin) instead of the intended 15:00 America/New_York.
 */
function toTZDate(dateStr: string, timeStr: string): Date {
    const localDt = new Date(`${dateStr}T${timeStr}`);
    const tzTime = new Date(localDt.toLocaleString('en-US', { timeZone: SHIFT_TIMEZONE }));
    const offset = localDt.getTime() - tzTime.getTime();
    return new Date(localDt.getTime() + offset);
}

export function Shifts() {
    const { canCreate, canDelete } = usePermission();
    const [activeTab, setActiveTab] = useState<'schedule' | 'templates'>('schedule');
    const [shifts, setShifts] = useState<Shift[]>([]);
    const [locations, setLocations] = useState<Location[]>([]);
    const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
    const [loading, setLoading] = useState(true);

    // Modal states
    const [showCreate, setShowCreate] = useState(false);
    const [expandedShiftId, setExpandedShiftId] = useState<number | null>(null);

    // Create Shift State
    const [createConfig, setCreateConfig] = useState({
        template_id: 0,
        start_date: '',
        repeat_weeks: false,
        assignments: {} as Record<number, number>
    });
    const [createError, setCreateError] = useState('');
    const [creating, setCreating] = useState(false);
    const [availableStaff, setAvailableStaff] = useState<Staff[]>([]);

    useEffect(() => {
        // Reload data when mounting or when switching to schedule tab
        // This ensures newly created templates appear in the dropdown
        if (activeTab === 'schedule') {
            loadData();
        }
    }, [activeTab]);

    // Fetch available staff when template AND date are both selected
    useEffect(() => {
        if (createConfig.template_id && createConfig.start_date) {
            api.getAvailableStaffForTemplate(createConfig.template_id, createConfig.start_date)
                .then(data => setAvailableStaff(data))
                .catch(err => console.error('Failed to fetch available staff:', err));
        } else {
            setAvailableStaff([]);
        }
    }, [createConfig.template_id, createConfig.start_date]);

    const loadData = async () => {
        setLoading(true);
        try {
            const [shiftsData, locationsData, templatesData] = await Promise.all([
                api.getShifts(),
                api.getLocations(),
                api.getShiftTemplates()
            ]);
            // Sort shifts by date (newest first)
            const sortedShifts = (shiftsData as Shift[]).sort((a, b) =>
                toTZDate(b.start_date, b.start_time).getTime() -
                toTZDate(a.start_date, a.start_time).getTime()
            );
            setShifts(sortedShifts);
            setLocations(locationsData);
            setTemplates(templatesData);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateShift = async () => {
        setCreateError('');
        if (!createConfig.template_id || !createConfig.start_date) {
            setCreateError('Please select a template and start date');
            return;
        }

        const template = templates.find(t => t.id === createConfig.template_id);
        if (template && template.shift_positions.some(pos => !createConfig.assignments[pos.id])) {
            setCreateError('Please assign a staff member to every position');
            return;
        }

        setCreating(true);
        try {
            await api.createShiftFromTemplate({
                shift_template_id: createConfig.template_id,
                start_date: createConfig.start_date,
                repeat_weeks: createConfig.repeat_weeks ? 4 : 1,
                assignments: createConfig.assignments
            });
            setShowCreate(false);
            setCreateConfig({ template_id: 0, start_date: '', repeat_weeks: false, assignments: {} });
            loadData();
        } catch (err: any) {
            const msg = err.detail || err.message || 'Failed to create shift';
            setCreateError(msg);
        } finally {
            setCreating(false);
        }
    };



    const handleDelete = (id: number) => {
        setConfirmation({
            isOpen: true,
            title: 'Delete Shift',
            message: 'Are you sure you want to delete this shift?',
            variant: 'danger',
            action: async () => {
                // Clear state
                setConfirmation(prev => ({ ...prev, error: undefined, isConfirmDisabled: false }));
                try {
                    await api.deleteShift(id);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    loadData();
                } catch (err: any) {
                    let errorMessage = 'Failed to delete shift';
                    let shouldDisable = false;

                    if (err.status === 409 || (err.message && err.message.includes('in use'))) {
                        errorMessage = 'Shift cannot be deleted because it has active assignments. Please remove all assignments first.';
                        shouldDisable = true;
                    } else if (err.message) {
                        errorMessage = err.message;
                    }

                    // Set error and disabled state
                    setConfirmation(prev => ({
                        ...prev,
                        error: errorMessage,
                        isConfirmDisabled: shouldDisable
                    }));
                }
            }
        });
    };

    // Edit Shift State
    const [editingShift, setEditingShift] = useState<Shift | null>(null);
    const [editConfig, setEditConfig] = useState({
        start_date: '',
        start_time: '',
        end_date: '',
        end_time: '',
        program_location_id: 0
    });
    const [updating, setUpdating] = useState(false);

    // Confirmation Modal State
    const [confirmation, setConfirmation] = useState<{
        isOpen: boolean;
        title: string;
        message: string;
        variant: 'danger' | 'primary' | 'warning';
        action: () => void;
        error?: string; // Add error field
        isConfirmDisabled?: boolean;
    }>({
        isOpen: false,
        title: '',
        message: '',
        variant: 'primary',
        action: () => { }
    });

    const handleEditClick = (shift: Shift) => {
        setEditingShift(shift);
        setEditConfig({
            start_date: shift.start_date,
            start_time: shift.start_time,
            end_date: shift.end_date,
            end_time: shift.end_time,
            program_location_id: shift.program_location_id
        });
    };

    const handleUpdateShift = async () => {
        if (!editingShift) return;
        setUpdating(true);
        try {
            await api.updateShift(editingShift.id, editConfig);
            setEditingShift(null);
            loadData();
        } catch (err: any) {
            alert(err.message || 'Failed to update shift');
        } finally {
            setUpdating(false);
        }
    };

    const getLocationName = (id: number) => locations.find(l => l.id === id)?.name || `Location ${id}`;
    const formatTime = (timeStr: string) => timeStr.substring(0, 5);
    const getTemplateName = (id: number | null) => {
        if (!id) return 'Custom';
        return templates.find(t => t.id === id)?.name || 'Unknown Template';
    };

    return (
        <div className="page">
            <div className="page-header">
                <h2>Shifts &amp; Schedule</h2>
            </div>

            <div className="tabs" style={{ marginBottom: '20px', borderBottom: '1px solid #ddd' }}>
                <button
                    style={{
                        padding: '10px 20px',
                        marginRight: '5px',
                        border: 'none',
                        background: 'none',
                        borderBottom: activeTab === 'schedule' ? '2px solid #0056b3' : 'none',
                        color: activeTab === 'schedule' ? '#0056b3' : '#666',
                        fontWeight: activeTab === 'schedule' ? 'bold' : 'normal',
                        cursor: 'pointer'
                    }}
                    onClick={() => setActiveTab('schedule')}
                >
                    Schedule
                </button>
                <button
                    style={{
                        padding: '10px 20px',
                        marginRight: '5px',
                        border: 'none',
                        background: 'none',
                        borderBottom: activeTab === 'templates' ? '2px solid #0056b3' : 'none',
                        color: activeTab === 'templates' ? '#0056b3' : '#666',
                        fontWeight: activeTab === 'templates' ? 'bold' : 'normal',
                        cursor: 'pointer'
                    }}
                    onClick={() => setActiveTab('templates')}
                >
                    Templates
                </button>
            </div>

            {activeTab === 'templates' ? (
                <ShiftTemplatesTab />
            ) : (
                <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', padding: '0 20px' }}>
                        <h3 style={{ margin: 0 }}>Schedule</h3>
                        {canCreate('shifts') && (
                            <button className="btn-primary" onClick={() => setShowCreate(true)}>
                                + New Shift
                            </button>
                        )}
                    </div>

                    {loading ? (
                        <p>Loading shifts...</p>
                    ) : (
                        <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: '30px' }}>
                            {shifts.length === 0 ? (
                                <p className="text-center text-muted">No shifts scheduled. Generate schedule or add shifts.</p>
                            ) : (
                                <div className="table-container">
                                    <table className="data-table">
                                        <thead>
                                            <tr>
                                                <th>Date</th>
                                                <th>Time</th>
                                                <th>Location</th>
                                                <th>Template</th>
                                                <th style={{ width: '180px' }}>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {[
                                                {
                                                    title: 'Current Shifts', data: shifts.filter(s => {
                                                        const now = getNow();
                                                        const start = toTZDate(s.start_date, s.start_time);
                                                        const end = toTZDate(s.end_date, s.end_time);
                                                        return now >= start && now <= end;
                                                    })
                                                },
                                                {
                                                    title: 'Future Shifts', data: shifts.filter(s => {
                                                        const now = getNow();
                                                        const start = toTZDate(s.start_date, s.start_time);
                                                        return now < start;
                                                    }).sort((a, b) => toTZDate(a.start_date, a.start_time).getTime() - toTZDate(b.start_date, b.start_time).getTime())
                                                },
                                                {
                                                    title: 'Past Shifts', data: shifts.filter(s => {
                                                        const now = getNow();
                                                        const end = toTZDate(s.end_date, s.end_time);
                                                        return now > end;
                                                    }).sort((a, b) => toTZDate(b.start_date, b.start_time).getTime() - toTZDate(a.start_date, a.start_time).getTime())
                                                }
                                            ].map((section, idx) => (
                                                section.data.length > 0 && (
                                                    <React.Fragment key={idx}>
                                                        <tr>
                                                            <td colSpan={5} style={{ background: '#fafafa', borderBottom: '1px solid #eee', padding: '15px 10px 5px 10px' }}>
                                                                <h4 style={{ margin: 0, color: '#666', textTransform: 'uppercase', fontSize: '12px', letterSpacing: '0.05em' }}>
                                                                    {section.title}
                                                                </h4>
                                                            </td>
                                                        </tr>
                                                        {section.data.map(shift => {
                                                            const isPast = section.title === 'Past Shifts';
                                                            return (
                                                                <React.Fragment key={shift.id}>
                                                                    <tr
                                                                        onClick={() => setExpandedShiftId(expandedShiftId === shift.id ? null : shift.id)}
                                                                        style={{ cursor: 'pointer', background: expandedShiftId === shift.id ? '#f8f9fa' : 'white' }}
                                                                    >
                                                                        <td>
                                                                            <span style={{ marginRight: '8px' }}>{expandedShiftId === shift.id ? '▼' : '▶'}</span>
                                                                            {new Date(shift.start_date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                                                                        </td>
                                                                        <td>{formatTime(shift.start_time)} - {formatTime(shift.end_time)}</td>
                                                                        <td>{getLocationName(shift.program_location_id)}</td>
                                                                        <td>{getTemplateName(shift.shift_template_id)}</td>
                                                                        <td onClick={e => e.stopPropagation()}>
                                                                            {section.title === 'Future Shifts' && (
                                                                                <button className="btn-sm" onClick={() => handleEditClick(shift)}>Edit</button>
                                                                            )}
                                                                            {canDelete('shifts') && !isPast && (
                                                                                <button className="btn-sm btn-danger" style={{ marginLeft: '4px' }} onClick={() => handleDelete(shift.id)}>
                                                                                    Delete
                                                                                </button>
                                                                            )}
                                                                        </td>
                                                                    </tr>
                                                                    {expandedShiftId === shift.id && (
                                                                        <tr>
                                                                            <td colSpan={5} style={{ background: '#f5f7fa', padding: 0, borderTop: 'none' }}>
                                                                                <div style={{
                                                                                    marginLeft: '40px',
                                                                                    borderLeft: '4px solid #3498db',
                                                                                    background: '#fff',
                                                                                    padding: '20px',
                                                                                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                                                                                }}>
                                                                                    <h3 style={{ marginTop: 0, marginBottom: '15px' }}>Assignments</h3>
                                                                                    <ShiftAssignments
                                                                                        shiftId={shift.id}
                                                                                        shiftTemplateId={shift.shift_template_id}
                                                                                        inline={true}
                                                                                        isReadOnly={isPast}
                                                                                    />
                                                                                </div>
                                                                            </td>
                                                                        </tr>
                                                                    )}
                                                                </React.Fragment>
                                                            );
                                                        })}
                                                    </React.Fragment>
                                                )
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}
                </>
            )}

            {showCreate && (
                <div className="modal-overlay" onClick={() => setShowCreate(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <h2>Create New Shift</h2>
                        {createError && (
                            <div className="alert-danger" style={{
                                marginBottom: '16px',
                                color: '#721c24',
                                backgroundColor: '#f8d7da',
                                borderColor: '#f5c6cb',
                                padding: '.75rem 1.25rem',
                                borderRadius: '0.25rem',
                                border: '1px solid transparent'
                            }}>
                                {createError}
                            </div>
                        )}
                        <div className="form-group">
                            <label>Select Template</label>
                            <select
                                value={createConfig.template_id}
                                onChange={e => setCreateConfig({ ...createConfig, template_id: Number(e.target.value) })}
                            >
                                <option value={0}>-- Select Template --</option>
                                {templates.map(t => (
                                    <option key={t.id} value={t.id} disabled={!t.is_active}>{t.name} ({DAYS[t.start_day_of_week]})</option>
                                ))}
                            </select>
                            {createConfig.template_id !== 0 && (
                                <div style={{ fontSize: '13px', color: '#666', marginTop: '5px' }}>
                                    Location: {getLocationName(templates.find(t => t.id === createConfig.template_id)?.program_location_id || 0)} <br />
                                    Time: {formatTime(templates.find(t => t.id === createConfig.template_id)?.start_time || '')} - {formatTime(templates.find(t => t.id === createConfig.template_id)?.end_time || '')}
                                </div>
                            )}
                        </div>

                        <div className="form-group">
                            <label>Start Date *</label>
                            <input
                                type="date"
                                min={new Date().toISOString().split('T')[0]}
                                value={createConfig.start_date}
                                onChange={e => setCreateConfig({ ...createConfig, start_date: e.target.value })}
                            />
                        </div>

                        {createConfig.template_id !== 0 && createConfig.start_date && (
                            <div className="form-group">
                                <label>Assign Staff (Required)</label>
                                <div style={{ background: '#f5f5f5', padding: '10px', borderRadius: '4px' }}>
                                    {templates.find(t => t.id === createConfig.template_id)?.shift_positions.map(pos => {
                                        // Exclude staff already assigned to OTHER positions in this shift
                                        const assignedToOthers = Object.entries(createConfig.assignments)
                                            .filter(([pId, val]) => Number(pId) !== pos.id && val)
                                            .map(([, val]) => Number(val));

                                        // availableStaff is pre-filtered by backend (excludes overlapping shifts)
                                        const positionAvailableStaff = availableStaff.filter(s =>
                                            !assignedToOthers.includes(s.id)
                                        );

                                        const clientNames = pos.clients && pos.clients.length > 0
                                            ? `(${pos.clients.map(c => c.client.first_name).join(', ')})`
                                            : '';

                                        return (
                                            <div key={pos.id} style={{ marginBottom: '8px' }}>
                                                <div style={{ fontSize: '13px', marginBottom: '2px', fontWeight: '500' }}>
                                                    {pos.position_name} {clientNames && <span style={{ fontWeight: 'normal', color: '#666' }}>{clientNames}</span>}
                                                </div>
                                                <select
                                                    value={createConfig.assignments[pos.id] || ''}
                                                    onChange={e => setCreateConfig({
                                                        ...createConfig,
                                                        assignments: {
                                                            ...createConfig.assignments,
                                                            [pos.id]: Number(e.target.value)
                                                        }
                                                    })}
                                                    style={{ width: '100%' }}
                                                >
                                                    <option value="">-- Unassigned --</option>
                                                    {positionAvailableStaff.map(s => (
                                                        <option key={s.id} value={s.id}>{s.first_name} {s.last_name} ({s.role_name || 'Staff'})</option>
                                                    ))}
                                                </select>
                                            </div>
                                        );
                                    })}
                                    {(!templates.find(t => t.id === createConfig.template_id)?.shift_positions?.length) && (
                                        <div style={{ fontSize: '12px', color: '#888' }}>No positions defined in this template.</div>
                                    )}
                                </div>
                            </div>
                        )}
                        <div className="form-group checkbox-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
                            <input
                                type="checkbox"
                                id="repeat"
                                checked={createConfig.repeat_weeks}
                                onChange={e => setCreateConfig({ ...createConfig, repeat_weeks: e.target.checked })}
                            />
                            <label htmlFor="repeat" style={{ marginBottom: 0 }}>Repeat weekly for one month (4 weeks)</label>
                        </div>
                        <div className="form-actions">
                            <button className="btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
                            <button
                                className="btn-primary"
                                onClick={handleCreateShift}
                                disabled={creating || !createConfig.template_id || !createConfig.start_date}
                            >
                                {creating ? 'Creating...' : 'Create Shift(s)'}
                            </button>
                        </div>
                    </div>
                </div>
            )
            }

            {editingShift && (
                <div className="modal-overlay" onClick={() => setEditingShift(null)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <h2>Edit Shift</h2>
                        <div className="form-group">
                            <label>Start Date</label>
                            <input
                                type="date"
                                min={new Date().toISOString().split('T')[0]}
                                value={editConfig.start_date}
                                onChange={e => setEditConfig({ ...editConfig, start_date: e.target.value })}
                            />
                        </div>
                        <div className="form-actions">
                            <button className="btn-secondary" onClick={() => setEditingShift(null)}>Cancel</button>
                            <button
                                className="btn-primary"
                                onClick={handleUpdateShift}
                                disabled={updating}
                            >
                                {updating ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    </div>
                </div>
            )}


            {/* Confirmation Modal */}
            <ConfirmationModal
                isOpen={confirmation.isOpen}
                title={confirmation.title}
                message={confirmation.message}
                variant={confirmation.variant}
                onConfirm={confirmation.action}
                onCancel={() => setConfirmation({ ...confirmation, isOpen: false, error: undefined, isConfirmDisabled: false })}
                error={confirmation.error}
                disableConfirm={confirmation.isConfirmDisabled}
            />
        </div>
    );
}
