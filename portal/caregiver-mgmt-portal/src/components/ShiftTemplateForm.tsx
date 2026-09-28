import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { ConfirmationModal } from './ConfirmationModal';

interface ShiftTemplateFormData {
    name: string;
    program_location_id: number;
    start_day_of_week: number;
    start_time: string;
    end_time: string;
    is_active: boolean;
    is_overnight: boolean;
}

interface Task {
    id: number;
    name: string;
}

interface Client {
    id: number;
    first_name: string;
    last_name: string;
    program_location_id?: number;
    is_active: boolean;
    active_enrollments?: { program_location_id: number; is_active: boolean }[];
}

interface ShiftPositionTask {
    id: number;
    shift_position_id: number;
    task_id: number;
    task?: Task;
}

interface ShiftPositionClient {
    id: number;
    shift_position_id: number;
    client_id: number;
    client?: Client;
}

interface ShiftPosition {
    id: number;
    shift_template_id: number;
    position_name: string;
    description?: string;
    tasks?: ShiftPositionTask[];
    clients?: ShiftPositionClient[];
}

interface Location {
    id: number;
    name: string;
}

interface ShiftTemplateFormProps {
    onCancel: () => void;
    initialData?: any;
    isEditing?: boolean;
    initialMode?: 'details' | 'positions';
}

// ... imports and consts ...

const DAYS_OF_WEEK = [
    { id: 0, name: 'Monday' },
    { id: 1, name: 'Tuesday' },
    { id: 2, name: 'Wednesday' },
    { id: 3, name: 'Thursday' },
    { id: 4, name: 'Friday' },
    { id: 5, name: 'Saturday' },
    { id: 6, name: 'Sunday' },
];



const defaultData: ShiftTemplateFormData = {
    name: '',
    program_location_id: 0,
    start_day_of_week: 0,
    start_time: '',
    end_time: '',
    is_active: true,
    is_overnight: false,
};

export function ShiftTemplateForm({ onCancel, initialData, isEditing, initialMode = 'details' }: ShiftTemplateFormProps) {
    // Mode: 'details' or 'positions'
    const [mode, setMode] = useState<'details' | 'positions'>(initialMode);
    const [data, setData] = useState<ShiftTemplateFormData>(initialData || defaultData);
    const [savedTemplateId, setSavedTemplateId] = useState<number | null>(initialData?.id || null);

    // Position Management State
    const [positions, setPositions] = useState<ShiftPosition[]>(initialData?.shift_positions || []);
    const [locations, setLocations] = useState<Location[]>([]);
    const [availableTasks, setAvailableTasks] = useState<Task[]>([]);
    const [availableClients, setAvailableClients] = useState<Client[]>([]);

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Inner Position Form
    const [showPosForm, setShowPosForm] = useState(false);
    const [posFormData, setPosFormData] = useState({ position_name: '', description: '', client_ids: [] as number[] });
    const [editingPosId, setEditingPosId] = useState<number | null>(null); // To support editing existing position

    // Inner Task Form
    const [addingTaskToPosId, setAddingTaskToPosId] = useState<number | null>(null);
    const [taskFormData, setTaskFormData] = useState({ task_id: 0, task_name: '', category_id: '' });
    const [categories, setCategories] = useState<{ id: number, name: string }[]>([]);

    // Confirmation Modal State
    const [deleteConfirmation, setDeleteConfirmation] = useState<{
        isOpen: boolean;
        type: 'position' | 'task' | null;
        id: number | null;
        error?: string;
        disableConfirm?: boolean;
    }>({ isOpen: false, type: null, id: null });

    // Check for inactive clients in current assignments
    const inactiveClientsInTemplate = positions.flatMap(p =>
        p.clients?.filter(c => c.client && c.client.is_active === false).map(c => `${c.client?.first_name} ${c.client?.last_name}`) || []
    );

    useEffect(() => {
        const loadLocs = async () => {
            try {
                const locs = await api.getLocations();
                setLocations(locs);
                if (!initialData && locs.length === 1) {
                    setData(prev => ({ ...prev, program_location_id: locs[0].id }));
                }
            } catch (e) { setError('Failed to load locations'); }
        };
        loadLocs();
        loadTasks();
        loadCategories();
        loadClients();
    }, [initialData]);

    const loadClients = async () => {
        try {
            const c = await api.getClients();
            setAvailableClients(c);
        } catch (e) { console.error('Failed to load clients'); }
    }

    const loadCategories = async () => {
        try {
            const c = await api.getTaskCategories();
            setCategories(c);
        } catch (e) { console.error('Failed to load categories'); }
    }

    const loadTasks = async () => {
        try {
            const t = await api.getTasks();
            setAvailableTasks(t);
        } catch (e) { console.error('Failed to load tasks'); }
    }

    const loadPositions = async () => {
        if (!savedTemplateId) return;
        try {
            const t = await api.getShiftTemplate(savedTemplateId);
            setPositions(t.shift_positions || []);
        } catch (e) { console.error('Failed to reload positions'); }
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value, type } = e.target;
        setData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked :
                name === 'program_location_id' || name === 'start_day_of_week' ? Number(value) :
                    value
        }));
    };



    const handleDetailsSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            if (!data.is_overnight && data.end_time <= data.start_time) {
                throw new Error("End time must be after start time, or mark as 'Overnight Shift'.");
            }

            let locationId = data.program_location_id;

            if (!locationId) {
                throw new Error('Please select a program location');
            }

            const submitData = { ...data, program_location_id: locationId };

            if (isEditing && savedTemplateId) {
                await api.updateShiftTemplate(savedTemplateId, submitData);
            } else {
                const res = await api.createShiftTemplate(submitData);
                setSavedTemplateId(res.id);
            }
            // Move to positions mode
            setMode('positions');
        } catch (err: any) {
            setError(err.message || 'Failed to save template');
        } finally {
            setLoading(false);
        }
    };

    // Position Actions
    const handleAddPosition = async () => {
        if (!savedTemplateId || !posFormData.position_name.trim()) return;
        try {
            const payload = {
                shift_template_id: savedTemplateId,
                ...posFormData
            };

            if (editingPosId) {
                await api.updateShiftPosition(editingPosId, payload);
            } else {
                await api.createShiftPosition(payload);
            }

            setPosFormData({ position_name: '', description: '', client_ids: [] });
            setShowPosForm(false);
            setEditingPosId(null);
            loadPositions();
        } catch (e) { alert('Failed to save position'); }
    };

    const handleEditPosition = (pos: ShiftPosition) => {
        setPosFormData({
            position_name: pos.position_name,
            description: pos.description || '',
            client_ids: pos.clients?.map(c => c.client_id) || []
        });
        setEditingPosId(pos.id);
        setShowPosForm(true);
    };

    const handleDeletePosition = async () => {
        if (!deleteConfirmation.id || deleteConfirmation.type !== 'position') return;
        // Clear previous error
        setDeleteConfirmation(prev => ({ ...prev, error: undefined, disableConfirm: false }));
        try {
            await api.deleteShiftPosition(deleteConfirmation.id);
            setDeleteConfirmation({ isOpen: false, type: null, id: null });
            loadPositions();
        } catch (e: any) {
            let errorMessage = 'Failed to delete position.';
            let shouldDisable = false;
            if (e.status === 409) {
                errorMessage = 'This position cannot be deleted because it is used in active shift assignments. Please remove all staff assignments using this position first.';
                shouldDisable = true;
            } else if (e.message) {
                errorMessage = e.message;
            }
            setDeleteConfirmation(prev => ({ ...prev, error: errorMessage, disableConfirm: shouldDisable }));
        }
    };

    // Task Actions
    const handleAddTask = async () => {
        if (!addingTaskToPosId || !taskFormData.task_name.trim()) return;
        try {
            let taskId = taskFormData.task_id;
            if (!taskId) {
                if (!taskFormData.category_id) {
                    alert("Please select a category for the new task.");
                    return;
                }
                const newTask = await api.createTask({
                    name: taskFormData.task_name,
                    category_id: Number(taskFormData.category_id),
                    is_custom: false
                });
                taskId = newTask.id;
                loadTasks(); // Refresh list
            }
            await api.createShiftPositionTask({
                shift_position_id: addingTaskToPosId,
                task_id: taskId
            });
            setTaskFormData({ task_id: 0, task_name: '', category_id: '' });
            setAddingTaskToPosId(null);
            loadPositions();
        } catch (e) { alert('Failed to add task'); }
    };

    const handleDeleteTask = async () => {
        if (!deleteConfirmation.id || deleteConfirmation.type !== 'task') return;
        try {
            await api.deleteShiftPositionTask(deleteConfirmation.id);
            setDeleteConfirmation({ isOpen: false, type: null, id: null });
            loadPositions();
        } catch (e) { alert('Failed to remove task'); }
    }

    const toggleClientSelection = (clientId: number) => {
        setPosFormData(prev => {
            const exists = prev.client_ids.includes(clientId);
            if (exists) {
                return { ...prev, client_ids: prev.client_ids.filter(id => id !== clientId) };
            } else {
                return { ...prev, client_ids: [...prev.client_ids, clientId] };
            }
        });
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" style={{ maxWidth: '800px', width: '90%' }} onClick={e => e.stopPropagation()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <h2>{isEditing ? 'Edit Shift Template' : 'Create New Template'}</h2>
                    {mode === 'positions' && (
                        <button className="btn-sm" onClick={() => setMode('details')}>Back to Details</button>
                    )}
                </div>

                {inactiveClientsInTemplate.length > 0 && (
                    <div style={{
                        marginBottom: '16px',
                        fontSize: '13px',
                        padding: '12px 16px',
                        backgroundColor: '#fff3cd',
                        border: '1px solid #ffc107',
                        borderRadius: '8px',
                        color: '#856404'
                    }}>
                        <strong>⚠️ Warning:</strong> This template contains inactive clients: {inactiveClientsInTemplate.join(', ')}.
                        Please remove them from positions.
                    </div>
                )}

                {error && <div className="error-message">{error}</div>}

                {/* DETAILS MODE */}
                {mode === 'details' && (
                    <form onSubmit={handleDetailsSubmit}>
                        <div className="form-group">
                            <label>Template Name *</label>
                            <input type="text" name="name" value={data.name} onChange={handleChange} required />
                        </div>

                        <div className="form-group">
                            <label>Location *</label>
                            <select name="program_location_id" value={data.program_location_id || ''} onChange={handleChange} required>
                                <option value="">Select Location</option>
                                {locations.map(loc => (
                                    <option key={loc.id} value={loc.id}>{loc.name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="form-group">
                            <label>Day of Week *</label>
                            <select name="start_day_of_week" value={data.start_day_of_week} onChange={handleChange} required>
                                {DAYS_OF_WEEK.map(day => (
                                    <option key={day.id} value={day.id}>{day.name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Start Time *</label>
                                <input type="time" name="start_time" value={data.start_time} onChange={handleChange} required />
                            </div>
                            <div className="form-group">
                                <label>End Time *</label>
                                <input type="time" name="end_time" value={data.end_time} onChange={handleChange} required />
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group checkbox-group">
                                <input type="checkbox" name="is_overnight" checked={data.is_overnight} onChange={handleChange} />
                                <label>Overnight Shift (ends next day)</label>
                            </div>
                            {isEditing && (
                                <div className="form-group checkbox-group">
                                    <input type="checkbox" name="is_active" checked={data.is_active} onChange={handleChange} />
                                    <label>Active</label>
                                </div>
                            )}
                        </div>

                        <div className="form-actions">
                            <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
                            <button type="submit" className="btn-primary" disabled={loading}>
                                {loading ? 'Saving...' : (isEditing ? 'Save Changes' : 'Next: Add Positions')}
                            </button>
                        </div>
                    </form>
                )}

                {/* POSITIONS MODE */}
                {mode === 'positions' && (
                    <div className="positions-manager">
                        <div style={{ background: '#f8f9fa', padding: '15px', borderRadius: '8px', marginBottom: '20px' }}>
                            <h4 style={{ margin: '0 0 10px 0' }}>Positions & Tasks</h4>
                            <p className="text-sm text-muted">Define the staff positions required for this shift and their specific tasks.</p>

                            {!showPosForm ? (
                                <button className="btn-sm btn-primary" onClick={() => {
                                    setPosFormData({ position_name: '', description: '', client_ids: [] });
                                    setEditingPosId(null);
                                    setShowPosForm(true);
                                }}>+ Add Position</button>
                            ) : (
                                <div style={{ background: 'white', padding: '10px', borderRadius: '4px', marginTop: '10px', border: '1px solid #ddd' }}>
                                    <div className="form-group">
                                        <label>Position Name</label>
                                        <input
                                            value={posFormData.position_name}
                                            onChange={e => setPosFormData({ ...posFormData, position_name: e.target.value })}
                                            placeholder="e.g. Staff A"
                                        />
                                    </div>
                                    <div className="form-group">
                                        <input
                                            value={posFormData.description}
                                            onChange={e => setPosFormData({ ...posFormData, description: e.target.value })}
                                            placeholder="Description (optional)"
                                        />
                                    </div>

                                    {/* Client Selection */}
                                    <div className="form-group">
                                        <label>Assigned Clients (Optional)</label>

                                        {/* Show currently assigned inactive clients with remove option */}
                                        {posFormData.client_ids.filter(id => {
                                            const client = availableClients.find(c => c.id === id);
                                            return client && client.is_active === false;
                                        }).length > 0 && (
                                                <div style={{
                                                    marginBottom: '8px',
                                                    padding: '8px',
                                                    backgroundColor: '#fff3cd',
                                                    borderRadius: '4px',
                                                    border: '1px solid #ffc107'
                                                }}>
                                                    <div style={{ fontSize: '12px', fontWeight: 'bold', color: '#856404', marginBottom: '4px' }}>
                                                        Inactive clients (click to remove):
                                                    </div>
                                                    {posFormData.client_ids
                                                        .map(id => availableClients.find(c => c.id === id))
                                                        .filter(c => c && c.is_active === false)
                                                        .map(client => client && (
                                                            <span
                                                                key={client.id}
                                                                onClick={() => toggleClientSelection(client.id)}
                                                                style={{
                                                                    display: 'inline-block',
                                                                    padding: '2px 8px',
                                                                    margin: '2px',
                                                                    backgroundColor: '#d32f2f',
                                                                    color: 'white',
                                                                    borderRadius: '12px',
                                                                    fontSize: '12px',
                                                                    cursor: 'pointer'
                                                                }}
                                                                title="Click to remove"
                                                            >
                                                                {client.first_name} {client.last_name.charAt(0)}. ×
                                                            </span>
                                                        ))
                                                    }
                                                </div>
                                            )}

                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px', maxHeight: '150px', overflowY: 'auto', border: '1px solid #eee', padding: '8px', borderRadius: '4px' }}>
                                            {availableClients.filter(c => {
                                                if (c.is_active === false) return false;

                                                if (data.program_location_id) {
                                                    const match = c.active_enrollments?.some(e => e.program_location_id === data.program_location_id && e.is_active);
                                                    return match;
                                                }
                                                // If no location selected, filter out everyone to prevent issues
                                                return false;
                                            }).map(client => (
                                                <label key={client.id} style={{ display: 'flex', alignItems: 'center', fontSize: '13px', cursor: 'pointer' }}>
                                                    <input
                                                        type="checkbox"
                                                        checked={posFormData.client_ids.includes(client.id)}
                                                        onChange={() => toggleClientSelection(client.id)}
                                                        style={{ marginRight: '6px' }}
                                                    />
                                                    {client.first_name} {client.last_name.charAt(0)}.
                                                </label>
                                            ))}
                                            {availableClients.filter(c => {
                                                if (c.is_active === false) return false;
                                                if (data.program_location_id) {
                                                    return c.active_enrollments?.some(e => e.program_location_id === data.program_location_id && e.is_active);
                                                }
                                                return false;
                                            }).length === 0 && (
                                                    <span className="text-muted text-sm" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '10px' }}>
                                                        {data.program_location_id ? "No active clients enrolled in this location." : "Please select a location first."}
                                                    </span>
                                                )}
                                        </div>
                                    </div>

                                    <div style={{ display: 'flex', gap: '10px' }}>
                                        <button className="btn-sm btn-primary" onClick={handleAddPosition}>{editingPosId ? 'Update' : 'Save'} Position</button>
                                        <button className="btn-sm btn-secondary" onClick={() => { setShowPosForm(false); setEditingPosId(null); }}>Cancel</button>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="positions-list" style={{ display: 'grid', gap: '15px', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                            {positions.map(pos => (
                                <div key={pos.id} style={{ border: '1px solid #eee', borderRadius: '6px', padding: '10px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #eee', paddingBottom: '8px', marginBottom: '8px' }}>
                                        <div>
                                            <strong>{pos.position_name}</strong>
                                            {pos.clients && pos.clients.length > 0 && (
                                                <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>
                                                    Clients: {pos.clients.map((c, i) => (
                                                        <span key={c.id}>
                                                            {i > 0 && ', '}
                                                            <span style={{
                                                                textDecoration: c.client?.is_active === false ? 'line-through' : 'none',
                                                                color: c.client?.is_active === false ? '#d32f2f' : 'inherit'
                                                            }}>
                                                                {c.client?.first_name}
                                                                {c.client?.is_active === false && ' (Inactive)'}
                                                            </span>
                                                        </span>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        <div>
                                            <button className="text-primary" style={{ marginRight: '8px' }} onClick={() => handleEditPosition(pos)}>Edit</button>
                                            <button className="text-danger" onClick={() => setDeleteConfirmation({ isOpen: true, type: 'position', id: pos.id })}>×</button>
                                        </div>
                                    </div>
                                    <ul style={{ paddingLeft: '20px', margin: '0 0 10px 0', fontSize: '13px' }}>
                                        {pos.tasks?.map(t => (
                                            <li key={t.id}>
                                                {t.task?.name}
                                                <span
                                                    onClick={() => setDeleteConfirmation({ isOpen: true, type: 'task', id: t.id })}
                                                    style={{ color: 'red', cursor: 'pointer', marginLeft: '6px' }}
                                                >×</span>
                                            </li>
                                        ))}
                                    </ul>

                                    {addingTaskToPosId === pos.id ? (
                                        <div style={{ marginTop: '8px' }}>
                                            <input
                                                list="task-list"
                                                value={taskFormData.task_name}
                                                onChange={e => {
                                                    const val = e.target.value;
                                                    const existing = availableTasks.find(t => t.name.toLowerCase() === val.toLowerCase());
                                                    setTaskFormData(prev => ({
                                                        ...prev,
                                                        task_name: val,
                                                        task_id: existing ? existing.id : 0
                                                    }));
                                                }}
                                                placeholder="Task name..."
                                                style={{ width: '100%', marginBottom: '4px', fontSize: '13px', padding: '4px' }}
                                                autoFocus
                                            />
                                            <datalist id="task-list">
                                                {availableTasks.map(t => <option key={t.id} value={t.name} />)}
                                            </datalist>

                                            {/* Show category dropdown if creating new task */}
                                            {taskFormData.task_name && !taskFormData.task_id && (
                                                <select
                                                    value={taskFormData.category_id}
                                                    onChange={e => setTaskFormData(prev => ({ ...prev, category_id: e.target.value }))}
                                                    style={{ width: '100%', marginBottom: '4px', fontSize: '12px', padding: '4px' }}
                                                >
                                                    <option value="">Select Category...</option>
                                                    {categories.map(c => (
                                                        <option key={c.id} value={c.id}>{c.name}</option>
                                                    ))}
                                                </select>
                                            )}

                                            <div style={{ display: 'flex', gap: '4px' }}>
                                                <button className="btn-xs btn-primary" onClick={handleAddTask}>Add</button>
                                                <button className="btn-xs btn-secondary" onClick={() => setAddingTaskToPosId(null)}>Cancel</button>
                                            </div>
                                        </div>
                                    ) : (
                                        <button className="btn-link" style={{ fontSize: '12px' }} onClick={() => {
                                            setAddingTaskToPosId(pos.id);
                                            setTaskFormData({ task_id: 0, task_name: '', category_id: '' });
                                        }}>+ Add Task</button>
                                    )}
                                </div>
                            ))}
                        </div>

                        <div className="form-actions" style={{ marginTop: '20px', borderTop: '1px solid #eee', paddingTop: '15px' }}>
                            <button className="btn-primary" onClick={onCancel}>Done</button>
                        </div>
                    </div>
                )}
            </div>

            <ConfirmationModal
                isOpen={deleteConfirmation.isOpen}
                title={deleteConfirmation.type === 'position' ? 'Delete Position' : 'Remove Task'}
                message={deleteConfirmation.type === 'position'
                    ? 'Are you sure you want to delete this position? All associated tasks will also be removed.'
                    : 'Are you sure you want to remove this task from the position?'}
                variant="danger"
                onConfirm={deleteConfirmation.type === 'position' ? handleDeletePosition : handleDeleteTask}
                onCancel={() => setDeleteConfirmation({ isOpen: false, type: null, id: null, error: undefined, disableConfirm: false })}
                error={deleteConfirmation.error}
                disableConfirm={deleteConfirmation.disableConfirm}
            />
        </div>
    );
}
