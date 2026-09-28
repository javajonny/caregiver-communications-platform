import { useState, useEffect } from 'react';
import { api, API_BASE } from '../services/api';

interface StaffFormData {
    first_name: string;
    last_name: string;
    work_email: string;
    work_phone: string;
    password?: string;
    role_id: number;
    assigned_location_id: number | null;
    is_active: boolean;
    profile_image_path?: string | null;
}

interface Location {
    id: number;
    name: string;
}

interface StaffFormProps {
    initialData?: StaffFormData;
    onSubmit: (data: StaffFormData, profileImage?: File | null) => Promise<void>;
    onCancel: () => void;
    isEditing?: boolean;
}

const defaultData: StaffFormData = {
    first_name: '',
    last_name: '',
    work_email: '',
    work_phone: '',
    password: '',
    role_id: 4, // Default to DSP
    assigned_location_id: null,
    is_active: true,
};

const ROLES = [
    { id: 1, name: 'Admin' },
    { id: 2, name: 'Director' },
    { id: 3, name: 'Site Director' },
    { id: 4, name: 'DSP' },
];

const SITE_DIRECTOR_ROLE_ID = ROLES.find(r => r.name === 'Site Director')?.id ?? 3;

export function StaffForm({ initialData, onSubmit, onCancel, isEditing }: StaffFormProps) {
    const [data, setData] = useState<StaffFormData>(initialData || defaultData);
    const [locations, setLocations] = useState<Location[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [profileImage, setProfileImage] = useState<File | null>(null);
    // Initialize preview with existing image if editing
    const existingImageUrl = initialData?.profile_image_path
        ? `${API_BASE}/uploads/staff/${initialData.profile_image_path}`
        : null;
    const [imagePreview, setImagePreview] = useState<string | null>(existingImageUrl);

    useEffect(() => {
        api.getLocations()
            .then(setLocations)
            .catch(() => setLocations([]));
    }, []);

    // Clear location if role changes away from Site Director
    useEffect(() => {
        if (data.role_id !== SITE_DIRECTOR_ROLE_ID) {
            setData(prev => ({ ...prev, assigned_location_id: null }));
        }
    }, [data.role_id]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value, type } = e.target;
        setData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked :
                name === 'role_id' ? Number(value) :
                    name === 'assigned_location_id' ? (value === '' ? null : Number(value)) :
                        value
        }));
    };

    const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setProfileImage(file);
            const reader = new FileReader();
            reader.onloadend = () => {
                setImagePreview(reader.result as string);
            };
            reader.readAsDataURL(file);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        // Validation
        if (!isEditing && (!data.password || data.password.length < 8)) {
            setError('Password must be at least 8 characters');
            setLoading(false);
            return;
        }

        if (data.role_id === SITE_DIRECTOR_ROLE_ID && !data.assigned_location_id) {
            setError('Site Director must have an assigned location');
            setLoading(false);
            return;
        }

        try {
            // Prepare data for submission
            const submitData = { ...data };
            if (isEditing) {
                delete submitData.password; // Don't send password on edit
            }

            await onSubmit(submitData, profileImage);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save staff member');
        } finally {
            setLoading(false);
        }
    };

    const isSiteDirector = data.role_id === SITE_DIRECTOR_ROLE_ID;

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '550px' }}>
                <h2>{isEditing ? 'Edit Staff Member' : 'Add Staff Member'}</h2>

                {error && <div className="error-message">{error}</div>}

                <form onSubmit={handleSubmit}>
                    {/* Profile Image */}
                    <div className="form-group" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{
                            width: '100px',
                            height: '100px',
                            borderRadius: '50%',
                            overflow: 'hidden',
                            backgroundColor: '#f0f0f0',
                            marginBottom: '10px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            {imagePreview ? (
                                <img src={imagePreview} alt="Preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (
                                <span style={{ fontSize: '36px', color: '#999' }}>👤</span>
                            )}
                        </div>
                        <label className="btn-sm btn-secondary" style={{ cursor: 'pointer' }}>
                            {imagePreview ? 'Change Photo' : 'Upload Photo'}
                            <input
                                type="file"
                                accept=".jpg,.jpeg"
                                onChange={handleImageChange}
                                style={{ display: 'none' }}
                            />
                        </label>
                        <small style={{ color: '#666', marginTop: '5px' }}>JPG/JPEG only</small>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>First Name *</label>
                            <input
                                type="text"
                                name="first_name"
                                value={data.first_name}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Last Name *</label>
                            <input
                                type="text"
                                name="last_name"
                                value={data.last_name}
                                onChange={handleChange}
                                required
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Work Email *</label>
                            <input
                                type="email"
                                name="work_email"
                                value={data.work_email}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Work Phone</label>
                            <input
                                type="tel"
                                name="work_phone"
                                value={data.work_phone}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {/* Password - only for new staff */}
                    {!isEditing && (
                        <div className="form-group">
                            <label>Temporary Password *</label>
                            <input
                                type="password"
                                name="password"
                                value={data.password || ''}
                                onChange={handleChange}
                                required
                                minLength={8}
                                placeholder="Min. 8 characters"
                            />
                            <small style={{ color: '#666', fontSize: '12px' }}>
                                User will be required to change password on first login
                            </small>
                        </div>
                    )}

                    <div className="form-row">
                        <div className="form-group">
                            <label>Role *</label>
                            <select name="role_id" value={data.role_id} onChange={handleChange} required>
                                {ROLES.map(role => (
                                    <option key={role.id} value={role.id}>{role.name}</option>
                                ))}
                            </select>
                        </div>

                        {/* Assigned Location - only for Site Director */}
                        {isSiteDirector && (
                            <div className="form-group">
                                <label>Assigned Location *</label>
                                <select
                                    name="assigned_location_id"
                                    value={data.assigned_location_id ?? ''}
                                    onChange={handleChange}
                                    required
                                >
                                    <option value="">Select Location...</option>
                                    {locations.map(loc => (
                                        <option key={loc.id} value={loc.id}>{loc.name}</option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>

                    <div className="form-row">
                        <div className="form-group checkbox-group">
                            <input
                                type="checkbox"
                                name="is_active"
                                checked={data.is_active}
                                onChange={handleChange}
                            />
                            <label>Active</label>
                        </div>
                    </div>

                    <div className="form-actions">
                        <button type="button" className="btn-secondary" onClick={onCancel}>
                            Cancel
                        </button>
                        <button type="submit" className="btn-primary" disabled={loading}>
                            {loading ? 'Saving...' : isEditing ? 'Update' : 'Create'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
