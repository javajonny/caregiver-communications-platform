import { useEffect, useState } from 'react';
import { api, API_BASE } from '../services/api';
import { StaffForm } from '../components/StaffForm';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { usePermission } from '../hooks/usePermission';

interface StaffMember {
    id: number;
    first_name: string;
    last_name: string;
    work_email: string;
    work_phone: string;
    role_id: number;
    assigned_location_id: number | null;
    is_active: boolean;
    profile_image_path?: string | null;
}

interface Location {
    id: number;
    name: string;
}

export function Staff() {
    const [staff, setStaff] = useState<StaffMember[]>([]);
    const [locations, setLocations] = useState<Location[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editingStaff, setEditingStaff] = useState<StaffMember | null>(null);
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

    const { canCreate, canUpdate, canDelete, isAdmin } = usePermission();

    const loadStaff = () => {
        setLoading(true);
        Promise.all([
            api.getStaff(),
            api.getLocations().catch(() => [])
        ])
            .then(([staffData, locData]) => {
                setStaff(staffData);
                setLocations(locData);
            })
            .catch(console.error)
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        loadStaff();
    }, []);

    const handleCreate = async (data: object, profileImage?: File | null) => {
        const result = await api.createStaff(data);
        // Upload profile image if provided
        if (profileImage && result.id) {
            try {
                await api.uploadStaffProfileImage(result.id, profileImage);
            } catch (err) {
                console.error('Failed to upload profile image:', err);
            }
        }
        setShowForm(false);
        loadStaff();
    };

    const handleDelete = (id: number) => {
        setConfirmation({
            isOpen: true,
            title: 'Deactivate Staff Member',
            message: 'Are you sure you want to deactivate this staff member? This will remove their access to the system and unassign them from all future shifts.',
            variant: 'danger',
            action: async () => {
                try {
                    const response = await api.deleteStaff(id);

                    // Show success message FIRST before any state updates
                    if (response?.message) {
                        setSuccessMessage(response.message);
                        // Auto-clear after 5 seconds
                        setTimeout(() => setSuccessMessage(null), 5000);
                    }

                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    loadStaff();
                } catch (err) {
                    console.error('Failed to delete staff:', err);
                    alert('Failed to deactivate staff member. They may be assigned to current shifts.');
                }
            }
        });
    };

    const handleReactivateStaff = async (id: number) => {
        try {
            await api.updateStaff(id, { is_active: true });
            setSuccessMessage('Staff member reactivated successfully');
            setTimeout(() => setSuccessMessage(null), 5000);
            loadStaff();
        } catch (err) {
            console.error('Failed to reactivate staff:', err);
            alert('Failed to reactivate staff member.');
        }
    };

    const handleUpdate = async (data: object, profileImage?: File | null) => {
        if (!editingStaff) return;
        await api.updateStaff(editingStaff.id, data);
        // Upload profile image if provided
        if (profileImage) {
            try {
                await api.uploadStaffProfileImage(editingStaff.id, profileImage);
            } catch (err) {
                console.error('Failed to upload profile image:', err);
            }
        }
        setEditingStaff(null);
        loadStaff();
    };

    const getRoleName = (roleId: number) => {
        const roles: Record<number, string> = {
            1: 'Admin',
            2: 'Director',
            3: 'Site Director',
            4: 'DSP',
        };
        return roles[roleId] || 'Unknown';
    };

    const getLocationName = (locationId: number | null) => {
        if (!locationId) return 'All Locations';
        const loc = locations.find(l => l.id === locationId);
        return loc?.name || `Location ${locationId}`;
    };

    const [resetModal, setResetModal] = useState<{
        isOpen: boolean;
        staffId: number | null;
        staffName: string;
        tempPassword: string;
    }>({
        isOpen: false,
        staffId: null,
        staffName: '',
        tempPassword: ''
    });

    const openResetModal = (member: StaffMember) => {
        setResetModal({
            isOpen: true,
            staffId: member.id,
            staffName: `${member.first_name} ${member.last_name}`,
            tempPassword: ''
        });
    };

    const handleResetPassword = async () => {
        if (!resetModal.staffId || !resetModal.tempPassword) return;

        try {
            await api.resetPassword(resetModal.staffId, resetModal.tempPassword);
            setSuccessMessage(`Password reset successfully for ${resetModal.staffName}`);
            setTimeout(() => setSuccessMessage(null), 5000);
            setResetModal(prev => ({ ...prev, isOpen: false, tempPassword: '' }));
        } catch (err: any) {
            console.error('Failed to reset password:', err);
            // Use the error message from the API if available
            const errorMessage = err.message || 'Failed to reset password. Please ensure it meets complexity requirements.';
            alert(errorMessage);
        }
    };

    return (
        <div className="page">
            <div className="page-header">
                <h2>Staff</h2>
                {canCreate('staff') && (
                    <button className="btn-primary" onClick={() => setShowForm(true)}>
                        + Add Staff
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
                <p>Loading staff...</p>
            ) : staff.length === 0 ? (
                <p className="text-muted">No staff found</p>
            ) : (
                <table className="data-table">
                    <thead>
                        <tr>
                            <th></th>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Location</th>
                            <th>Status</th>
                            {(canUpdate('staff') || canDelete('staff')) && <th>Actions</th>}
                        </tr>
                    </thead>
                    <tbody>
                        {staff.map(member => (
                            <tr key={member.id}>
                                <td style={{ width: '50px', padding: '8px' }}>
                                    <div style={{
                                        width: '40px',
                                        height: '40px',
                                        borderRadius: '50%',
                                        background: '#e0e0e0',
                                        overflow: 'hidden',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
                                    }}>
                                        {member.profile_image_path ? (
                                            <img
                                                src={`${API_BASE}/uploads/staff/${member.profile_image_path}`}
                                                alt=""
                                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                                onError={(e) => {
                                                    console.warn('Failed to load image:', member.profile_image_path);
                                                    e.currentTarget.style.display = 'none';
                                                    e.currentTarget.parentElement!.innerHTML = '<span style="font-size:12px;color:#999">N/A</span>';
                                                }}
                                            />
                                        ) : (
                                            <span style={{ fontSize: '18px', color: '#999' }}>👤</span>
                                        )}
                                    </div>
                                </td>
                                <td>{member.first_name} {member.last_name}</td>
                                <td>{member.work_email}</td>
                                <td>{getRoleName(member.role_id)}</td>
                                <td>{getLocationName(member.assigned_location_id)}</td>
                                <td>
                                    <span className={`status ${member.is_active ? 'active' : 'inactive'}`}>
                                        {member.is_active ? 'Active' : 'Inactive'}
                                    </span>
                                </td>
                                {(canUpdate('staff') || canDelete('staff')) && (
                                    <td>
                                        {canUpdate('staff') && member.is_active && (
                                            <>
                                                <button className="btn-sm" onClick={() => setEditingStaff(member)}>
                                                    Edit
                                                </button>
                                                {/* Reset Password Button - Admin Only */}
                                                {isAdmin() && (
                                                    <button
                                                        className="btn-sm"
                                                        onClick={() => openResetModal(member)}
                                                        style={{ marginLeft: '8px', backgroundColor: '#6c757d', color: 'white', border: 'none' }}
                                                        title="Reset Password"
                                                    >
                                                        🔓 Reset
                                                    </button>
                                                )}
                                            </>
                                        )}
                                        {canDelete('staff') && member.is_active && (
                                            <button
                                                className="btn-sm btn-danger"
                                                onClick={() => handleDelete(member.id)}
                                                style={{ marginLeft: '8px' }}
                                            >
                                                Delete
                                            </button>
                                        )}
                                        {canUpdate('staff') && !member.is_active && (
                                            <button
                                                className="btn-sm btn-primary"
                                                onClick={() => handleReactivateStaff(member.id)}
                                            >
                                                Reactivate
                                            </button>
                                        )}
                                    </td>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}

            {showForm && canCreate('staff') && (
                <StaffForm
                    onSubmit={handleCreate}
                    onCancel={() => setShowForm(false)}
                />
            )}

            {editingStaff && canUpdate('staff') && (
                <StaffForm
                    initialData={editingStaff}
                    onSubmit={handleUpdate}
                    onCancel={() => setEditingStaff(null)}
                    isEditing
                />
            )}

            {resetModal.isOpen && (
                <div className="modal-overlay">
                    <div className="modal" style={{ maxWidth: '400px' }}>
                        <h3>Reset Password for {resetModal.staffName}</h3>
                        <p className="text-muted" style={{ fontSize: '0.9em', marginBottom: '1rem' }}>
                            The user will be required to change this password immediately upon their next login.
                        </p>

                        <div className="form-group">
                            <label>Temporary Password</label>
                            <input
                                type="text"
                                className="form-control"
                                value={resetModal.tempPassword}
                                onChange={(e) => setResetModal(prev => ({ ...prev, tempPassword: e.target.value }))}
                                placeholder="e.g. Temp123!"
                            />
                            <small className="text-muted" style={{ fontSize: '0.75em', marginTop: '4px' }}>
                                Minimum 8 characters, including uppercase, lowercase, number, and special character.
                            </small>
                        </div>

                        <div className="form-actions">
                            <button
                                className="btn-secondary"
                                onClick={() => setResetModal(prev => ({ ...prev, isOpen: false }))}
                            >
                                Cancel
                            </button>
                            <button
                                className="btn-primary"
                                onClick={handleResetPassword}
                                disabled={!resetModal.tempPassword || resetModal.tempPassword.length < 8}
                            >
                                Reset Password
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
                onCancel={() => setConfirmation(prev => ({ ...prev, isOpen: false }))}
            />
        </div>
    );
}
