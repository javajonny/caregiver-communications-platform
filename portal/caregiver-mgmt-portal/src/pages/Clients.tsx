import { useEffect, useState } from 'react';
import { api, API_BASE } from '../services/api';
import { ClientForm } from '../components/ClientForm';
import { ContactForm } from '../components/ContactForm';
import { EnrollmentForm } from '../components/EnrollmentForm';
import { ResidenceForm } from '../components/ResidenceForm';
import { BehaviorConfigModal } from '../components/BehaviorConfigModal';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { usePermission } from '../hooks/usePermission';

interface Client {
    id: number;
    first_name: string;
    last_name: string;
    date_of_birth: string;
    gender: string;
    race: string;
    height_feet: number;
    height_inches: number;
    profile_image_path?: string;
    is_active: boolean;
}

interface ProgramEnrollment {
    id: number;
    client_id: number;
    program_location_id: number;
    location_name?: string;
    start_date: string;
    end_date: string | null;
    is_active: boolean;
}

interface ClientContact {
    id: number;
    client_id: number;
    contact_first_name: string;
    contact_last_name: string;
    contact_phone_primary: string;
    contact_phone_secondary?: string;
    contact_email?: string;
    relationship: number;
    relationship_name?: string;
    is_primary: boolean;
    is_emergency_contact?: boolean;
    is_active: boolean;
}

interface ClientResidence {
    id: number;
    residence_type_id: number;
    address_id: number;
    start_date: string;
    end_date?: string | null;
}

interface BehaviorTrackingRecord {
    id: number;
    recorded_at: string;
    recorded_value: number;
    notes?: string;
    behavior_type: {
        id: number;
        name: string;
    };
    staff: {
        id: number;
        first_name: string;
        last_name: string;
    };
}

interface ClientUpdate {
    id: number;
    client_id: number;
    created_by: number;
    content: string;
    is_archived: boolean;
    created_at: string;
    author_name: string;
    is_read: boolean;
}





// BehaviorConfigItem kept for reference but BehaviorConfigVersion moved to component

export function Clients() {
    const [clients, setClients] = useState<Client[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingClient, setEditingClient] = useState<Client | null>(null);
    const [expandedClientId, setExpandedClientId] = useState<number | null>(null);
    const [enrollments, setEnrollments] = useState<ProgramEnrollment[]>([]);
    const [contacts, setContacts] = useState<ClientContact[]>([]);
    const [residence, setResidence] = useState<ClientResidence | null>(null);
    const [residenceHistory, setResidenceHistory] = useState<ClientResidence[]>([]);
    const [detailsLoading, setDetailsLoading] = useState(false);
    const [locations, setLocations] = useState<{ id: number; name: string }[]>([]);
    const [residenceTypes, setResidenceTypes] = useState<{ id: number; name: string }[]>([]);
    const [addresses, setAddresses] = useState<{ id: number; street_line_1: string; city: string; state_province: string }[]>([]);

    // Behavior tracking state
    const [behaviors, setBehaviors] = useState<BehaviorTrackingRecord[]>([]);
    const [visibleBehaviorCount, setVisibleBehaviorCount] = useState(10);

    // Client updates state
    const [clientUpdates, setClientUpdates] = useState<ClientUpdate[]>([]);
    const [visibleUpdatesCount, setVisibleUpdatesCount] = useState(5);

    // Modal states
    const [showContactForm, setShowContactForm] = useState(false);
    const [editingContact, setEditingContact] = useState<ClientContact | null>(null);
    const [showEnrollmentForm, setShowEnrollmentForm] = useState(false);
    const [showResidenceForm, setShowResidenceForm] = useState(false);

    // Behavior config management state
    const [showBehaviorModal, setShowBehaviorModal] = useState(false);

    // Success message state
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    // Confirmation Modal State
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

    const { canCreate, canUpdate, canDelete } = usePermission();

    const loadClients = () => {
        setLoading(true);
        api.getClients()
            .then(setClients)
            .catch(console.error)
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        loadClients();
        Promise.all([
            api.getLocations(),
            api.getResidenceTypes(),
            api.getAddresses(),
        ]).then(([locs, resTypes, addrs]) => {
            setLocations(locs);
            setResidenceTypes(resTypes);
            setAddresses(addrs);
        }).catch(console.error);
    }, []);

    const handleCreate = async (data: object) => {
        return await api.createClient(data);
    };

    const handleUpdate = async (data: object) => {
        if (!editingClient) return;
        return await api.updateClient(editingClient.id, data);
    };

    const handleSuccess = () => {
        setShowForm(false);
        setEditingClient(null);
        loadClients();
    };

    const handleDelete = (id: number) => {
        setConfirmation({
            isOpen: true,
            title: 'Deactivate Client',
            message: 'Are you sure you want to deactivate this client? This will archive them but preserve all records for HIPAA compliance.',
            variant: 'danger',
            action: async () => {
                try {
                    await api.deleteClient(id);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    setSuccessMessage('Client deactivated successfully');
                    setTimeout(() => setSuccessMessage(null), 5000);
                    loadClients();
                } catch (err) {
                    alert('Failed to deactivate client');
                }
            }
        });
    };

    const handleReactivateClient = async (id: number) => {
        try {
            await api.updateClient(id, { is_active: true });
            setSuccessMessage('Client reactivated successfully');
            setTimeout(() => setSuccessMessage(null), 5000);
            loadClients();
        } catch (err) {
            console.error('Failed to reactivate client:', err);
            alert('Failed to reactivate client');
        }
    };

    const loadClientDetails = async (clientId: number) => {
        setDetailsLoading(true);
        try {
            const [history, enrolls, conts, bhvrs, updates] = await Promise.all([
                api.getClientResidenceHistory(clientId).catch(() => []),
                api.getClientEnrollments(clientId),
                api.getClientContacts(clientId),
                api.getClientBehaviors(clientId),
                api.getClientUpdates(clientId)
            ]);

            const current = history.find((r: ClientResidence) => !r.end_date) || null;
            setResidence(current);
            setResidenceHistory(history);
            setContacts(conts);
            setBehaviors(bhvrs);
            setClientUpdates(updates);

            const enrichedEnrollments = enrolls.map((e: ProgramEnrollment) => ({
                ...e,
                location_name: locations.find(l => l.id === e.program_location_id)?.name || 'Unknown'
            }));
            setEnrollments(enrichedEnrollments);

        } catch (error) {
            console.error('Failed to load client details:', error);
        } finally {
            setDetailsLoading(false);
        }
    };

    const toggleDetails = async (clientId: number) => {
        if (expandedClientId === clientId) {
            setExpandedClientId(null);
            return;
        }
        setExpandedClientId(clientId);
        await loadClientDetails(clientId);
    };

    const refreshDetails = async () => {
        // Refresh locations in case a new one was created
        api.getLocations().then(setLocations).catch(console.error);
        if (expandedClientId) {
            loadClientDetails(expandedClientId);
        }
    };

    // Behavior config management handlers
    const openBehaviorModal = () => {
        if (!expandedClientId) return;
        setShowBehaviorModal(true);
    };



    // Contact handlers
    const handleDeleteContact = (contactId: number) => {
        setConfirmation({
            isOpen: true,
            title: 'Delete Contact',
            message: 'Are you sure you want to delete this contact?',
            variant: 'danger',
            action: async () => {
                try {
                    await api.deleteClientContact(contactId);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    if (expandedClientId) loadClientDetails(expandedClientId);
                } catch (err) {
                    console.error('Failed to delete contact', err);
                    alert('Failed to delete contact');
                }
            }
        });
    };

    const handleReactivateContact = async (contactId: number) => {
        try {
            await api.updateClientContact(contactId, { is_active: true });
            setSuccessMessage('Contact reactivated successfully');
            setTimeout(() => setSuccessMessage(null), 5000);
            if (expandedClientId) loadClientDetails(expandedClientId);
        } catch (err) {
            console.error('Failed to reactivate contact', err);
            alert('Failed to reactivate contact');
        }
    };

    // Enrollment handlers
    // Enrollment handlers
    const handleEndEnrollment = (enrollmentId: number) => {
        setConfirmation({
            isOpen: true,
            title: 'End Enrollment',
            message: 'Are you sure you want to end this enrollment? This will set the end date to today and preserve the history.',
            variant: 'danger',
            action: async () => {
                try {
                    await api.deleteClientEnrollment(enrollmentId);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    setSuccessMessage('Enrollment ended successfully');
                    setTimeout(() => setSuccessMessage(null), 5000);
                    refreshDetails();
                } catch (err: any) {
                    const errorMessage = err?.message || 'Failed to end enrollment';
                    alert(errorMessage);
                }
            }
        });
    };

    // Residence handlers
    // Residence handlers
    const handleEndResidence = () => {
        if (!expandedClientId) return;
        setConfirmation({
            isOpen: true,
            title: 'End Current Residence',
            message: 'Are you sure you want to end this residence? This will set the end date to today and preserve the history.',
            variant: 'danger',
            action: async () => {
                try {
                    await api.endClientResidence(expandedClientId);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    setSuccessMessage('Residence ended successfully');
                    setTimeout(() => setSuccessMessage(null), 5000);
                    if (expandedClientId) loadClientDetails(expandedClientId);
                } catch (err: any) {
                    const errorMessage = err?.message || 'Failed to end residence';
                    alert(errorMessage);
                }
            }
        });
    };

    return (
        <div className="page">
            <div className="page-header">
                <h2>Clients</h2>
                {canCreate('clients') && (
                    <button className="btn-primary" onClick={() => setShowForm(true)}>
                        + Add Client
                    </button>
                )}
            </div>

            {successMessage && (
                <div style={{
                    padding: '12px 16px',
                    marginBottom: '16px',
                    backgroundColor: '#d4edda',
                    border: '1px solid #c3e6cb',
                    borderRadius: '8px',
                    color: '#155724',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <span>{successMessage}</span>
                    <button
                        onClick={() => setSuccessMessage(null)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '16px', color: '#155724' }}
                    >
                        ×
                    </button>
                </div>
            )}

            {loading ? (
                <p>Loading clients...</p>
            ) : clients.length === 0 ? (
                <p className="text-muted">No clients found</p>
            ) : (
                <table className="data-table">
                    <thead>
                        <tr>
                            <th style={{ width: '50px' }}></th>
                            <th>Name</th>
                            <th>Date of Birth</th>
                            <th>Gender</th>
                            <th>Status</th>
                            {(canUpdate('clients') || canDelete('clients')) && <th>Actions</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {clients.map(client => (
                            <>
                                <tr
                                    key={client.id}
                                    onClick={() => toggleDetails(client.id)}
                                    style={{ cursor: 'pointer', background: expandedClientId === client.id ? '#f8f9fa' : 'white' }}
                                >
                                    <td style={{ padding: '8px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <span style={{ fontSize: '12px', width: '12px' }}>
                                                {expandedClientId === client.id ? '▼' : '▶'}
                                            </span>
                                            <div style={{
                                                width: '40px',
                                                height: '40px',
                                                borderRadius: '50%',
                                                overflow: 'hidden',
                                                backgroundColor: '#f0f0f0',
                                                border: '1px solid #ddd',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center'
                                            }}>
                                                <img
                                                    src={`${API_BASE}/uploads/clients/${client.profile_image_path || 'placeholder.jpg'}`}
                                                    alt={`${client.first_name}'s profile`}
                                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                                    onError={(e) => {
                                                        e.currentTarget.style.display = 'none';
                                                        e.currentTarget.parentElement!.innerHTML = '<span style="font-size:12px;color:#999;display:flex;align-items:center;justify-content:center;height:100%">N/A</span>';
                                                    }}
                                                />
                                            </div>
                                        </div>
                                    </td>
                                    <td>{client.first_name} {client.last_name}</td>
                                    <td>{client.date_of_birth}</td>
                                    <td>{client.gender}</td>
                                    <td>
                                        <span className={`status ${client.is_active ? 'active' : 'inactive'}`}>
                                            {client.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    {(canUpdate('clients') || canDelete('clients')) && (
                                        <td onClick={e => e.stopPropagation()}>
                                            {canUpdate('clients') && client.is_active && (
                                                <button className="btn-sm" onClick={() => setEditingClient(client)}>
                                                    Edit
                                                </button>
                                            )}
                                            {canDelete('clients') && client.is_active && (
                                                <button className="btn-sm btn-danger" onClick={() => handleDelete(client.id)}>
                                                    Delete
                                                </button>
                                            )}
                                            {canUpdate('clients') && !client.is_active && (
                                                <button className="btn-sm btn-primary" onClick={() => handleReactivateClient(client.id)}>
                                                    Reactivate
                                                </button>
                                            )}
                                        </td>
                                    )}
                                </tr>
                                {expandedClientId === client.id && (
                                    <tr key={`${client.id}-details`}>
                                        <td colSpan={6} style={{ background: '#f5f7fa', padding: '0', borderTop: 'none' }}>
                                            <div style={{
                                                marginLeft: '40px',
                                                borderLeft: '4px solid #3498db',
                                                background: '#fff',
                                                padding: '20px',
                                                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                                            }}>
                                                {detailsLoading ? (
                                                    <p>Loading details...</p>
                                                ) : (
                                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                                                        {/* Residence */}
                                                        <div style={{ overflow: 'hidden' }}>
                                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                                                <h4 style={{ margin: 0 }}>Current Residence</h4>
                                                                {canCreate('client_current_residence') && !residence && client.is_active && (
                                                                    <button className="btn-sm btn-primary" onClick={() => setShowResidenceForm(true)}>+ Set</button>
                                                                )}
                                                                {canDelete('client_current_residence') && residence && client.is_active && (
                                                                    <button className="btn-sm btn-danger" onClick={handleEndResidence}>End Residence</button>
                                                                )}
                                                            </div>
                                                            {residence ? (
                                                                <div style={{ fontSize: '14px', color: '#333', background: '#fff', padding: '12px', borderRadius: '8px', border: '1px solid #e0e0e0' }}>
                                                                    <div style={{ marginBottom: '8px' }}>
                                                                        <strong>Type:</strong> {residenceTypes.find(rt => rt.id === residence.residence_type_id)?.name || 'Unknown'}
                                                                    </div>
                                                                    <div style={{ marginBottom: '8px' }}>
                                                                        <strong>Address:</strong> {(() => {
                                                                            const addr = addresses.find(a => a.id === residence.address_id);
                                                                            return addr ? `${addr.street_line_1}, ${addr.city}, ${addr.state_province}` : 'Unknown';
                                                                        })()}
                                                                    </div>
                                                                    <div style={{ marginTop: '8px', color: '#666', fontSize: '14px' }}>
                                                                        Moved in: {residence.start_date}
                                                                        {residence.end_date && ` | Moved out: ${residence.end_date}`}
                                                                    </div>
                                                                </div>
                                                            ) : (
                                                                <p className="text-muted">No current residence set</p>
                                                            )}

                                                            {/* Residence History */}
                                                            {residenceHistory.length > 0 && residenceHistory.some(r => r.end_date) && (
                                                                <div style={{ marginTop: '16px', borderTop: '1px solid #eee', paddingTop: '16px' }}>
                                                                    <div style={{ fontSize: '13px', fontWeight: 'bold', color: '#666', marginBottom: '8px' }}>Residence History</div>
                                                                    <table style={{ width: '100%', fontSize: '12px' }}>
                                                                        <thead>
                                                                            <tr style={{ color: '#999', textAlign: 'left' }}>
                                                                                <th>Address</th>
                                                                                <th>Type</th>
                                                                                <th>Period</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {residenceHistory.filter(r => r.end_date).map(hist => {
                                                                                const type = residenceTypes.find(t => t.id === hist.residence_type_id);
                                                                                const addr = addresses.find(a => a.id === hist.address_id);
                                                                                return (
                                                                                    <tr key={hist.id} style={{ borderBottom: '1px solid #f5f5f5' }}>
                                                                                        <td style={{ padding: '4px 0' }}>{addr ? `${addr.street_line_1}, ${addr.city}` : 'Unknown'}</td>
                                                                                        <td style={{ padding: '4px 0' }}>{type?.name || 'Unknown'}</td>
                                                                                        <td style={{ padding: '4px 0' }}>{hist.start_date} — {hist.end_date}</td>
                                                                                    </tr>
                                                                                );
                                                                            })}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            )}
                                                        </div>

                                                        {/* Program Enrollments */}
                                                        <div style={{ overflow: 'hidden' }}>
                                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                                                <h4 style={{ margin: 0 }}>Program Enrollments</h4>
                                                                {canCreate('client_program_enrollments') && client.is_active && (
                                                                    <button className="btn-sm btn-primary" onClick={() => setShowEnrollmentForm(true)}>+ Add</button>
                                                                )}
                                                            </div>
                                                            {enrollments.length === 0 ? (
                                                                <p className="text-muted">No enrollments</p>
                                                            ) : (
                                                                <table className="data-table" style={{ fontSize: '14px' }}>
                                                                    <thead>
                                                                        <tr>
                                                                            <th>Location</th>
                                                                            <th>Start</th>
                                                                            <th>Status</th>
                                                                            {canDelete('client_program_enrollments') && <th>Actions</th>}
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody>
                                                                        {enrollments.map(e => (
                                                                            <tr key={e.id}>
                                                                                <td>{locations.find(l => l.id === e.program_location_id)?.name || 'Unknown'}</td>
                                                                                <td>{e.start_date}</td>
                                                                                <td>
                                                                                    <span className={`status ${e.end_date ? 'inactive' : 'active'}`}>
                                                                                        {e.end_date ? `Ended ${e.end_date}` : 'Active'}
                                                                                    </span>
                                                                                </td>
                                                                                {canDelete('client_program_enrollments') && (
                                                                                    <td style={{ whiteSpace: 'nowrap' }}>
                                                                                        {client.is_active && !e.end_date && (
                                                                                            <button className="btn-sm btn-danger" onClick={() => handleEndEnrollment(e.id)}>End Enrollment</button>
                                                                                        )}
                                                                                    </td>
                                                                                )}
                                                                            </tr>
                                                                        ))}
                                                                    </tbody>
                                                                </table>
                                                            )}
                                                        </div>

                                                        {/* Contacts */}
                                                        <div style={{ overflow: 'hidden' }}>
                                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                                                <h4 style={{ margin: 0 }}>Contacts</h4>
                                                                {canCreate('client_contacts') && client.is_active && (
                                                                    <button className="btn-sm btn-primary" onClick={() => setShowContactForm(true)}>+ Add</button>
                                                                )}
                                                            </div>
                                                            {contacts.length === 0 ? (
                                                                <p className="text-muted">No contacts</p>
                                                            ) : (
                                                                <table className="data-table" style={{ fontSize: '14px' }}>
                                                                    <thead>
                                                                        <tr>
                                                                            <th>Name</th>
                                                                            <th>Phone</th>
                                                                            <th>Primary</th>
                                                                            {(canUpdate('client_contacts') || canDelete('client_contacts')) && <th>Actions</th>}
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody>
                                                                        {contacts.map(c => (
                                                                            <tr key={c.id}>
                                                                                <td>{c.contact_first_name} {c.contact_last_name}</td>
                                                                                <td>{c.contact_phone_primary}</td>
                                                                                <td>{c.is_primary ? '✓' : ''}</td>
                                                                                {(canUpdate('client_contacts') || canDelete('client_contacts')) && (
                                                                                    <td style={{ whiteSpace: 'nowrap' }}>
                                                                                        <div style={{ display: 'flex', gap: '4px' }}>
                                                                                            {canUpdate('client_contacts') && c.is_active && client.is_active && (
                                                                                                <button className="btn-sm" onClick={() => setEditingContact(c)}>Edit</button>
                                                                                            )}
                                                                                            {canDelete('client_contacts') && c.is_active && client.is_active && (
                                                                                                <button className="btn-sm btn-danger" onClick={() => handleDeleteContact(c.id)}>Delete</button>
                                                                                            )}
                                                                                            {canUpdate('client_contacts') && !c.is_active && client.is_active && (
                                                                                                <button className="btn-sm btn-primary" onClick={() => handleReactivateContact(c.id)}>Reactivate</button>
                                                                                            )}
                                                                                        </div>
                                                                                    </td>
                                                                                )}
                                                                            </tr>
                                                                        ))}
                                                                    </tbody>
                                                                </table>
                                                            )}
                                                        </div>

                                                        {/* Behavioral Health Section */}
                                                        <div style={{ overflow: 'hidden' }}>
                                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                                                <h4 style={{ margin: 0 }}>Behavior Tracking</h4>
                                                                {(canCreate('client_behavior_configs') || canUpdate('client_behavior_configs')) && client.is_active && (
                                                                    <button
                                                                        className="btn-sm btn-secondary"
                                                                        onClick={openBehaviorModal}
                                                                        style={{ fontSize: '12px' }}
                                                                    >
                                                                        Manage Behaviors
                                                                    </button>
                                                                )}
                                                            </div>
                                                            {behaviors.length === 0 ? (
                                                                <p className="text-muted">No behavior records found</p>
                                                            ) : (
                                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                                                                    {/* Summary Cards */}
                                                                    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                                                                        <div style={{
                                                                            flex: '1', minWidth: '150px',
                                                                            background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '12px',
                                                                            boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                                                                        }}>
                                                                            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>Total Incidents (30d)</div>
                                                                            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2c3e50' }}>
                                                                                {behaviors.reduce((sum, b) => sum + b.recorded_value, 0)}
                                                                            </div>
                                                                        </div>
                                                                        <div style={{
                                                                            flex: '1', minWidth: '150px',
                                                                            background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '12px',
                                                                            boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                                                                        }}>
                                                                            <div style={{ fontSize: '12px', color: '#666', marginBottom: '4px' }}>Most Frequent</div>
                                                                            <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#e74c3c' }}>
                                                                                {(() => {
                                                                                    if (!behaviors.length) return '—';
                                                                                    const counts: Record<string, number> = {};
                                                                                    for (const b of behaviors) {
                                                                                        const name = b.behavior_type?.name || 'Unknown';
                                                                                        counts[name] = (counts[name] || 0) + b.recorded_value;
                                                                                    }
                                                                                    const top = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];
                                                                                    return top ? `${top[0]} (${top[1]})` : '—';
                                                                                })()}
                                                                            </div>
                                                                        </div>
                                                                    </div>

                                                                    {/* Weekly Summary Section */}
                                                                    {(() => {
                                                                        // Group behaviors by week
                                                                        const getWeekStart = (date: Date) => {
                                                                            const d = new Date(date);
                                                                            d.setHours(0, 0, 0, 0);
                                                                            d.setDate(d.getDate() - d.getDay()); // Sunday start
                                                                            return d.toISOString().split('T')[0];
                                                                        };

                                                                        // Get all behavior types
                                                                        const behaviorTypesSet = new Set<string>();
                                                                        behaviors.forEach(b => behaviorTypesSet.add(b.behavior_type?.name || 'Unknown'));
                                                                        const allBehaviorTypes = Array.from(behaviorTypesSet).sort();

                                                                        // Group by week
                                                                        const weeklyData: Record<string, Record<string, number>> = {};
                                                                        behaviors.forEach(b => {
                                                                            const weekStart = getWeekStart(new Date(b.recorded_at));
                                                                            const typeName = b.behavior_type?.name || 'Unknown';
                                                                            if (!weeklyData[weekStart]) {
                                                                                weeklyData[weekStart] = {};
                                                                                allBehaviorTypes.forEach(t => weeklyData[weekStart][t] = 0);
                                                                            }
                                                                            weeklyData[weekStart][typeName] = (weeklyData[weekStart][typeName] || 0) + b.recorded_value;
                                                                        });

                                                                        const sortedWeeks = Object.keys(weeklyData).sort().reverse();
                                                                        const maxTotal = Math.max(...sortedWeeks.map(w =>
                                                                            Object.values(weeklyData[w]).reduce((a, b) => a + b, 0)
                                                                        ), 1);

                                                                        // Colors for behaviors
                                                                        const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6', '#1abc9c', '#e67e22'];

                                                                        return (
                                                                            <div style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '16px' }}>
                                                                                <h5 style={{ margin: '0 0 12px 0', fontSize: '14px', color: '#333' }}>Weekly Summary</h5>

                                                                                {/* Bar Chart */}
                                                                                <div style={{ marginBottom: '16px' }}>
                                                                                    {sortedWeeks.slice(0, 6).map((week) => {
                                                                                        const weekEnd = new Date(week);
                                                                                        weekEnd.setDate(weekEnd.getDate() + 6);
                                                                                        const total = Object.values(weeklyData[week]).reduce((a, b) => a + b, 0);

                                                                                        return (
                                                                                            <div key={week} style={{ marginBottom: '8px' }}>
                                                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                                                                                                    <span style={{ fontSize: '11px', color: '#666', width: '90px', flexShrink: 0 }}>
                                                                                                        {new Date(week).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} {' - '}{weekEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                                                                                                    </span>
                                                                                                    <div style={{ flex: 1, display: 'flex', height: '20px', borderRadius: '4px', overflow: 'hidden', background: '#f0f0f0' }}>
                                                                                                        {allBehaviorTypes.map((type, typeIdx) => {
                                                                                                            const value = weeklyData[week][type] || 0;
                                                                                                            if (value === 0) return null;
                                                                                                            const width = (value / maxTotal) * 100;
                                                                                                            return (
                                                                                                                <div
                                                                                                                    key={type}
                                                                                                                    style={{
                                                                                                                        width: `${width}%`,
                                                                                                                        background: colors[typeIdx % colors.length],
                                                                                                                        display: 'flex',
                                                                                                                        alignItems: 'center',
                                                                                                                        justifyContent: 'center'
                                                                                                                    }}
                                                                                                                    title={`${type}: ${value}`}
                                                                                                                />
                                                                                                            );
                                                                                                        })}
                                                                                                    </div>
                                                                                                    <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#333', width: '30px', textAlign: 'right' }}>
                                                                                                        {total}
                                                                                                    </span>
                                                                                                </div>
                                                                                            </div>
                                                                                        );
                                                                                    })}
                                                                                </div>

                                                                                {/* Legend */}
                                                                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
                                                                                    {allBehaviorTypes.map((type, idx) => (
                                                                                        <div key={type} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                                                            <div style={{ width: '12px', height: '12px', borderRadius: '2px', background: colors[idx % colors.length] }} />
                                                                                            <span style={{ fontSize: '11px', color: '#666' }}>{type}</span>
                                                                                        </div>
                                                                                    ))}
                                                                                </div>

                                                                                {/* Weekly Table */}
                                                                                <table className="data-table" style={{ fontSize: '12px' }}>
                                                                                    <thead>
                                                                                        <tr>
                                                                                            <th>Week</th>
                                                                                            {allBehaviorTypes.map(t => <th key={t}>{t}</th>)}
                                                                                            <th>Total</th>
                                                                                        </tr>
                                                                                    </thead>
                                                                                    <tbody>
                                                                                        {sortedWeeks.slice(0, 6).map(week => {
                                                                                            const weekEnd = new Date(week);
                                                                                            weekEnd.setDate(weekEnd.getDate() + 6);
                                                                                            const total = Object.values(weeklyData[week]).reduce((a, b) => a + b, 0);
                                                                                            return (
                                                                                                <tr key={week}>
                                                                                                    <td style={{ whiteSpace: 'nowrap' }}>
                                                                                                        {new Date(week).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} -
                                                                                                        {weekEnd.toLocaleDateString('en-US', { day: 'numeric' })}
                                                                                                    </td>
                                                                                                    {allBehaviorTypes.map(t => (
                                                                                                        <td key={t} style={{ textAlign: 'center' }}>
                                                                                                            {weeklyData[week][t] || 0}
                                                                                                        </td>
                                                                                                    ))}
                                                                                                    <td style={{ fontWeight: 'bold', textAlign: 'center' }}>{total}</td>
                                                                                                </tr>
                                                                                            );
                                                                                        })}
                                                                                    </tbody>
                                                                                </table>
                                                                            </div>
                                                                        );
                                                                    })()}

                                                                    {/* Detailed Records Table */}
                                                                    <details style={{ background: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '12px' }}>
                                                                        <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 500, color: '#333' }}>
                                                                            Show Detailed Records ({behaviors.length} records)
                                                                        </summary>
                                                                        <table className="data-table" style={{ fontSize: '14px', marginTop: '12px' }}>
                                                                            <thead>
                                                                                <tr>
                                                                                    <th>Date/Time</th>
                                                                                    <th>Type</th>
                                                                                    <th>Value</th>
                                                                                    <th>Staff</th>
                                                                                    <th>Notes</th>
                                                                                </tr>
                                                                            </thead>
                                                                            <tbody>
                                                                                {behaviors.slice(0, visibleBehaviorCount).map(b => (
                                                                                    <tr key={b.id}>
                                                                                        <td>{new Date(b.recorded_at).toLocaleString()}</td>
                                                                                        <td>
                                                                                            <span style={{
                                                                                                display: 'inline-block', padding: '2px 8px', borderRadius: '12px', fontSize: '12px',
                                                                                                background: '#e0f7fa', color: '#006064', border: '1px solid #b2ebf2'
                                                                                            }}>
                                                                                                {b.behavior_type?.name || 'Unknown'}
                                                                                            </span>
                                                                                        </td>
                                                                                        <td>{b.recorded_value}</td>
                                                                                        <td>{b.staff.first_name} {b.staff.last_name}</td>
                                                                                        <td style={{ color: '#666', fontSize: '13px' }}>{b.notes || '—'}</td>
                                                                                    </tr>
                                                                                ))}
                                                                            </tbody>
                                                                        </table>
                                                                        {behaviors.length > visibleBehaviorCount && (
                                                                            <div style={{ textAlign: 'center', marginTop: '8px' }}>
                                                                                <button
                                                                                    className="btn-sm"
                                                                                    style={{ background: '#f5f5f5', border: '1px solid #ddd', color: '#666' }}
                                                                                    onClick={() => setVisibleBehaviorCount(prev => prev + 10)}
                                                                                >
                                                                                    Show More ({behaviors.length - visibleBehaviorCount} remaining)
                                                                                </button>
                                                                            </div>
                                                                        )}
                                                                    </details>
                                                                </div>
                                                            )}
                                                        </div>

                                                        {/* Client Updates Section */}
                                                        <div style={{ overflow: 'hidden' }}>
                                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                                                <h4 style={{ margin: 0 }}>Caregiver Updates</h4>
                                                            </div>
                                                            {clientUpdates.length === 0 ? (
                                                                <p className="text-muted">No updates for this client</p>
                                                            ) : (
                                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                                                                    {clientUpdates.slice(0, visibleUpdatesCount).map(update => (
                                                                        <div
                                                                            key={update.id}
                                                                            style={{
                                                                                background: '#fff',
                                                                                border: '1px solid #e0e0e0',
                                                                                borderRadius: '8px',
                                                                                padding: '12px',
                                                                                boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                                                                            }}
                                                                        >
                                                                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                                                                <span style={{ fontWeight: 'bold', color: '#2c3e50' }}>
                                                                                    {update.author_name}
                                                                                </span>
                                                                                <span style={{ fontSize: '12px', color: '#666' }}>
                                                                                    {new Date(update.created_at).toLocaleString()}
                                                                                </span>
                                                                            </div>
                                                                            <p style={{ margin: 0, color: '#333', whiteSpace: 'pre-wrap' }}>
                                                                                {update.content}
                                                                            </p>
                                                                        </div>
                                                                    ))}
                                                                    {clientUpdates.length > visibleUpdatesCount && (
                                                                        <div style={{ textAlign: 'center' }}>
                                                                            <button
                                                                                className="btn-sm"
                                                                                style={{ background: '#f5f5f5', border: '1px solid #ddd', color: '#666' }}
                                                                                onClick={() => setVisibleUpdatesCount(prev => prev + 5)}
                                                                            >
                                                                                Show More ({clientUpdates.length - visibleUpdatesCount} remaining)
                                                                            </button>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                )}
                            </>
                        ))}
                    </tbody>
                </table>
            )}

            {/* Client Form */}
            {showForm && canCreate('clients') && (
                <ClientForm
                    onSubmit={handleCreate}
                    onCancel={() => setShowForm(false)}
                    onSuccess={handleSuccess}
                />
            )}

            {editingClient && canUpdate('clients') && (
                <ClientForm
                    initialData={editingClient}
                    onSubmit={handleUpdate}
                    onCancel={() => setEditingClient(null)}
                    onSuccess={handleSuccess}
                    isEditing
                />
            )}

            {/* Contact Form */}
            {(showContactForm || editingContact) && expandedClientId && (
                <ContactForm
                    clientId={expandedClientId}
                    initialData={editingContact || undefined}
                    isEditing={!!editingContact}
                    onSubmit={() => {
                        setShowContactForm(false);
                        setEditingContact(null);
                        refreshDetails();
                    }}
                    onCancel={() => {
                        setShowContactForm(false);
                        setEditingContact(null);
                    }}
                />
            )}

            {/* Enrollment Form */}
            {/* Enrollment Form */}
            {showEnrollmentForm && expandedClientId && (
                <EnrollmentForm
                    clientId={expandedClientId}
                    onSubmit={() => {
                        setShowEnrollmentForm(false);
                        refreshDetails();
                    }}
                    onCancel={() => {
                        setShowEnrollmentForm(false);
                    }}
                />
            )}

            {/* Residence Form */}
            {showResidenceForm && expandedClientId && (
                <ResidenceForm
                    clientId={expandedClientId}
                    initialData={residence ? {
                        residence_type_id: residence.residence_type_id,
                        address_id: residence.address_id,
                        start_date: residence.start_date
                    } : undefined}
                    hasExisting={!!residence}
                    residenceId={residence?.id}
                    onSubmit={() => {
                        setShowResidenceForm(false);
                        refreshDetails();
                    }}
                    onCancel={() => setShowResidenceForm(false)}
                />
            )}

            {/* Behavior Config Modal */}
            {showBehaviorModal && expandedClientId && (
                <BehaviorConfigModal
                    clientId={expandedClientId}
                    onSubmit={() => {
                        setShowBehaviorModal(false);
                        loadClientDetails(expandedClientId);
                    }}
                    onCancel={() => setShowBehaviorModal(false)}
                />
            )}

            {/* Confirmation Modal */}
            <ConfirmationModal
                isOpen={confirmation.isOpen}
                title={confirmation.title}
                message={confirmation.message}
                variant={confirmation.variant}
                onConfirm={confirmation.action}
                onCancel={() => setConfirmation(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
}
