import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { usePermission } from '../hooks/usePermission';
import { ShiftTemplateForm } from '../components/ShiftTemplateForm';
import { ConfirmationModal } from '../components/ConfirmationModal';

// Interfaces matching Backend Schemas
interface Task {
    id: number;
    name: string;
    description?: string;
    category_id?: number;
    is_custom: boolean;
}

interface ShiftPositionTask {
    id: number;
    shift_position_id: number;
    task_id: number;
    scheduled_start_time?: string;
    scheduled_end_time?: string;
    task: Task;
}

interface ShiftPosition {
    id: number;
    shift_template_id: number;
    position_name: string;
    description?: string;
    tasks: ShiftPositionTask[];
    clients?: ShiftPositionClient[];
}

interface Client {
    id: number;
    first_name: string;
    last_name: string;
    is_active: boolean;
}

interface ShiftPositionClient {
    id: number;
    client_id: number;
    client?: Client;
}

interface ShiftTemplate {
    id: number;
    name: string;
    program_location_id: number;
    start_day_of_week: number;
    start_time: string;
    end_time: string;
    is_active: boolean;
    is_overnight: boolean;
    shift_positions: ShiftPosition[];
}

interface Location {
    id: number;
    name: string;
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function ShiftTemplatesTab() {
    const { canCreate, canUpdate, canDelete } = usePermission();
    const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
    const [locations, setLocations] = useState<Location[]>([]);
    const [loading, setLoading] = useState(true);

    // Modal / Form States
    const [showCreateTemplate, setShowCreateTemplate] = useState(false);
    const [selectedTemplate, setSelectedTemplate] = useState<ShiftTemplate | null>(null);

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [templatesData, locationsData] = await Promise.all([
                api.getShiftTemplates(),
                api.getLocations()
            ]);
            setTemplates(templatesData);
            setLocations(locationsData);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    // Confirmation Modal State
    const [deleteConfirmation, setDeleteConfirmation] = useState<{
        isOpen: boolean;
        templateId: number | null;
    }>({ isOpen: false, templateId: null });

    const handleDeleteTemplate = async () => {
        if (!deleteConfirmation.templateId) return;
        try {
            await api.deleteShiftTemplate(deleteConfirmation.templateId);
            setDeleteConfirmation({ isOpen: false, templateId: null });
            loadData();
        } catch (err: any) {
            alert(err.message || 'Failed to delete template');
        }
    };

    const getLocationName = (id: number) => locations.find(l => l.id === id)?.name || `Location ${id}`;
    const formatTime = (timeStr: string) => timeStr.substring(0, 5);

    const [expandedTemplateId, setExpandedTemplateId] = useState<number | null>(null);
    const [formMode, setFormMode] = useState<'details' | 'positions'>('details');

    const toggleExpand = (id: number) => {
        setExpandedTemplateId(prev => prev === id ? null : id);
    };

    return (
        <div style={{ padding: '0 20px 20px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{ margin: 0 }}>Shift Templates</h3>
                {canCreate('shifts') && (
                    <button className="btn-primary" onClick={() => { setFormMode('details'); setShowCreateTemplate(true); }}>
                        + New Template
                    </button>
                )}
            </div>

            {loading ? <p>Loading...</p> : (
                <div className="table-container">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Location</th>
                                <th>Day</th>
                                <th>Time</th>
                                <th style={{ width: '150px' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {templates.map(template => (
                                <><tr key={template.id} onClick={() => toggleExpand(template.id)} style={{ cursor: 'pointer', background: expandedTemplateId === template.id ? '#f8f9fa' : 'white' }}>
                                    <td>
                                        <span style={{ marginRight: '8px' }}>{expandedTemplateId === template.id ? '▼' : '▶'}</span>
                                        {template.name}
                                        <span className="text-muted" style={{ marginLeft: '10px', fontSize: '12px' }}>
                                            ({template.shift_positions?.length || 0} pos)
                                        </span>
                                        {template.shift_positions?.some(pos =>
                                            pos.clients?.some(c => c.client?.is_active === false)
                                        ) && (
                                                <span style={{
                                                    marginLeft: '8px',
                                                    color: '#856404',
                                                    // backgroundColor: '#fff3cd',
                                                    padding: '2px 6px',
                                                    borderRadius: '4px',
                                                    fontSize: '11px',
                                                    fontWeight: 'bold'
                                                }} title="Contains inactive clients">
                                                    ⚠️
                                                </span>
                                            )}
                                    </td>
                                    <td>{getLocationName(template.program_location_id)}</td>
                                    <td>{DAYS[template.start_day_of_week]}</td>
                                    <td>{formatTime(template.start_time)} - {formatTime(template.end_time)}</td>
                                    <td onClick={e => e.stopPropagation()} style={{ whiteSpace: 'nowrap' }}>
                                        {canUpdate('shifts') && (
                                            <button className="btn-sm" onClick={() => { setFormMode('details'); setSelectedTemplate(template); }}>Edit</button>
                                        )}
                                        {canDelete('shifts') && (
                                            <button className="btn-sm btn-danger" onClick={() => setDeleteConfirmation({ isOpen: true, templateId: template.id })} style={{ marginLeft: '4px' }}>Delete</button>
                                        )}
                                    </td>
                                </tr>
                                    {expandedTemplateId === template.id && (
                                        <tr key={`${template.id}-expanded`} style={{ background: '#f8f9fa' }}>
                                            <td colSpan={5} style={{ background: '#f5f7fa', padding: 0, borderTop: 'none' }}>
                                                <div style={{
                                                    marginLeft: '40px',
                                                    borderLeft: '4px solid #3498db',
                                                    background: '#fff',
                                                    padding: '20px',
                                                    boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                                                }}>
                                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                                                        <h4 style={{ margin: 0 }}>Positions & Tasks</h4>
                                                        <button
                                                            className="btn-sm btn-primary"
                                                            onClick={() => {
                                                                setFormMode('positions');
                                                                setSelectedTemplate(template);
                                                            }}
                                                        >
                                                            Manage Positions
                                                        </button>
                                                    </div>

                                                    {template.shift_positions?.length === 0 ? <p className="text-muted">No positions defined.</p> : (
                                                        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                                                            {template.shift_positions?.map(pos => (
                                                                <div key={pos.id} style={{ border: '1px solid #eee', padding: '15px', borderRadius: '8px', flex: '1', minWidth: '250px' }}>
                                                                    <h5 style={{ marginTop: 0, marginBottom: '10px', fontSize: '15px', borderBottom: '1px solid #f0f0f0', paddingBottom: '8px' }}>{pos.position_name}</h5>
                                                                    {pos.clients && pos.clients.length > 0 && (
                                                                        <div style={{ fontSize: '12px', marginBottom: '8px', color: '#0056b3' }}>
                                                                            <span role="img" aria-label="clients" style={{ marginRight: '4px' }}>👥</span>
                                                                            {pos.clients.map((c, i) => (
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
                                                                    <ul style={{ margin: '5px 0 0 20px', padding: 0, fontSize: '13px', lineHeight: '1.6', color: '#555' }}>
                                                                        {pos.tasks?.map(t => (
                                                                            <li key={t.id}>{t.task?.name}</li>
                                                                        ))}
                                                                    </ul>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    )}</>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {(showCreateTemplate || selectedTemplate) && (
                <ShiftTemplateForm
                    onCancel={() => { setShowCreateTemplate(false); setSelectedTemplate(null); loadData(); }}
                    initialData={selectedTemplate || undefined}
                    isEditing={!!selectedTemplate}
                    initialMode={formMode}
                />
            )}

            <ConfirmationModal
                isOpen={deleteConfirmation.isOpen}
                title="Delete Template"
                message="Are you sure you want to delete this template? This cannot be undone."
                variant="danger"
                onConfirm={handleDeleteTemplate}
                onCancel={() => setDeleteConfirmation({ isOpen: false, templateId: null })}
            />
        </div>
    );
}
