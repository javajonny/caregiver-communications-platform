import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface ClientFormData {
    id?: number;
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

interface ResidenceData {
    id?: number;
    residence_type_id: number | null;
    address_id: number | null;
    established_date: string;
}

interface NewAddressData {
    street_line_1: string;
    street_line_2: string;
    city: string;
    state_province: string;
    postal_code: string;
    country: string;
}

interface EnrollmentData {
    program_location_id: number | null;
    start_date: string;
}

interface NewLocationData {
    name: string;
    location_type_id: number | null;
    address_id: number | null;
}

interface ClientFormProps {
    initialData?: ClientFormData;
    onSubmit: (data: ClientFormData) => Promise<{ id: number } | void>;
    onCancel: () => void;
    onSuccess: () => void;
    isEditing?: boolean;
}

const defaultData: ClientFormData = {
    first_name: '',
    last_name: '',
    date_of_birth: '',
    gender: '',
    race: '',
    height_feet: 5,
    height_inches: 0,
    is_active: true,
};

const defaultResidence: ResidenceData = {
    id: undefined,
    residence_type_id: null,
    address_id: null,
    established_date: new Date().toISOString().split('T')[0],
};

const defaultNewAddress: NewAddressData = {
    street_line_1: '',
    street_line_2: '',
    city: '',
    state_province: '',
    postal_code: '',
    country: 'USA',
};

const defaultEnrollment: EnrollmentData = {
    program_location_id: null,
    start_date: new Date().toISOString().split('T')[0],
};

const defaultNewLocation: NewLocationData = {
    name: '',
    location_type_id: null,
    address_id: null,
};

interface ResidenceType { id: number; name: string; }
interface ProgramLocation { id: number; name: string; }
interface LocationType { id: number; name: string; }

export function ClientForm({ initialData, onSubmit, onCancel, onSuccess, isEditing }: ClientFormProps) {
    const [data, setData] = useState<ClientFormData>(initialData || defaultData);
    const [residence, setResidence] = useState<ResidenceData>(defaultResidence);
    const [enrollment, setEnrollment] = useState<EnrollmentData>(defaultEnrollment);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Lookup data
    const [residenceTypes, setResidenceTypes] = useState<ResidenceType[]>([]);
    const [programLocations, setProgramLocations] = useState<ProgramLocation[]>([]);
    const [locationTypes, setLocationTypes] = useState<LocationType[]>([]);

    // Inline creation toggles
    const [showNewLocation, setShowNewLocation] = useState(false);
    const [newAddress, setNewAddress] = useState<NewAddressData>(defaultNewAddress);
    const [newLocation, setNewLocation] = useState<NewLocationData>(defaultNewLocation);
    const [newLocationAddress, setNewLocationAddress] = useState<NewAddressData>(defaultNewAddress);

    // Image Upload State
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const [selectedImage, setSelectedImage] = useState<File | null>(null);



    // Track if existing residence loaded
    const [hasExistingResidence, setHasExistingResidence] = useState(false);

    useEffect(() => {
        // Load lookup data
        Promise.all([
            api.getResidenceTypes(),
            api.getLocations(),
            api.getLocationTypes(),
        ]).then(([resTypes, locs, locTypes]) => {
            setResidenceTypes(resTypes);
            setProgramLocations(locs);
            setLocationTypes(locTypes);
        }).catch(console.error);

        // If editing, fetch residence
        if (isEditing && initialData?.id) {
            // Set initial image preview if exists

            api.getClientResidence(initialData.id)
                .then(res => {
                    setResidence({
                        id: res.id,
                        residence_type_id: res.residence_type_id,
                        address_id: res.address_id,
                        established_date: res.established_date || new Date().toISOString().split('T')[0]
                    });
                    setHasExistingResidence(true);
                })
                .catch(() => {
                    // Ignore 404/error, just means no residence or fetch failed
                    setHasExistingResidence(false);
                });
        }
    }, [isEditing, initialData?.id, initialData?.profile_image_path]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value, type } = e.target;
        setData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked :
                type === 'number' ? Number(value) : value
        }));
    };

    const handleResidenceChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setResidence(prev => ({
            ...prev,
            [name]: name.endsWith('_id') ? (value ? Number(value) : null) : value
        }));
    };

    const handleEnrollmentChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setEnrollment(prev => ({
            ...prev,
            [name]: name.endsWith('_id') ? (value ? Number(value) : null) : value
        }));
    };

    const handleNewAddressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setNewAddress(prev => ({ ...prev, [name]: value }));
    };

    const handleNewLocationChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setNewLocation(prev => ({
            ...prev,
            [name]: name.endsWith('_id') ? (value ? Number(value) : null) : value
        }));
    };

    const handleNewLocationAddressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setNewLocationAddress(prev => ({ ...prev, [name]: value }));
    };

    const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setSelectedImage(file);

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

        try {
            // Step 1: Create new address if needed
            // Step 1: Create new address if needed
            let addressId = residence.address_id;
            // Always create new address for residence if entered
            if (newAddress.street_line_1) {
                const createdAddress = await api.createAddress(newAddress);
                addressId = createdAddress.id;
            }

            // Step 2: Create new program location if needed
            let locationId = enrollment.program_location_id;
            if (showNewLocation && newLocation.name) {
                let locationAddressId = newLocation.address_id;

                // Always create new address for location
                if (newLocationAddress.street_line_1) {
                    const createdLocAddress = await api.createAddress(newLocationAddress);
                    locationAddressId = createdLocAddress.id;
                } else if (!locationAddressId) {
                    // Check if valid addressId from residence exists to fallback? 
                    // With strict privacy, maybe we shouldn't fallback implicitly unless logic dictates.
                    // But let's keep the fallback if it's the SAME submission flow?
                    // Actually, if we just created addressId above, we can use it.
                    locationAddressId = addressId;
                }

                const createdLocation = await api.createProgramLocation({
                    ...newLocation,
                    address_id: locationAddressId,
                });
                locationId = createdLocation.id;
                setProgramLocations(prev => [...prev, createdLocation]);
            }

            // Step 3: Create client
            const result = await onSubmit(data);
            const clientId = result && 'id' in result ? result.id : (isEditing && initialData?.id ? initialData.id : null);

            if (clientId) {
                // Step 4: Create or Update residence
                if (residence.residence_type_id && addressId) {
                    const residenceData = {
                        residence_type_id: residence.residence_type_id,
                        address_id: addressId,
                        established_date: residence.established_date,
                    };

                    if (isEditing && hasExistingResidence && residence.id) {
                        await api.updateClientResidence(clientId, residence.id, residenceData);
                    } else {
                        // Create new (for new client OR existing client with no prior residence)
                        await api.createClientResidence({
                            client_id: clientId,
                            ...residenceData
                        });
                    }
                }

                if (!isEditing && locationId) {
                    await api.createClientEnrollment({
                        client_id: clientId,
                        program_location_id: locationId,
                        start_date: enrollment.start_date,
                        is_active: true,
                    });
                }

                // Step 6: Upload profile image if selected
                if (selectedImage) {
                    await api.uploadClientProfileImage(clientId, selectedImage);
                }

                onSuccess();
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save client');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '700px', maxHeight: '90vh', overflow: 'auto' }}>
                <h2>{isEditing ? 'Edit Client' : 'Add Client'}</h2>

                {error && <div className="error-message">{error}</div>}

                <form onSubmit={handleSubmit}>
                    {/* Basic Info Section */}
                    <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '20px' }}>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{
                                width: '100px',
                                height: '100px',
                                borderRadius: '50%',
                                overflow: 'hidden',
                                backgroundColor: '#f0f0f0',
                                margin: '0 auto 10px',
                                border: '1px solid #ddd',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center'
                            }}>
                                {imagePreview ? (
                                    <img
                                        src={imagePreview}
                                        alt="Preview"
                                        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                        onError={(e) => {
                                            // Provide fallback if preview fails
                                            e.currentTarget.style.display = 'none';
                                            e.currentTarget.parentElement!.innerHTML = '<span>N/A</span>';
                                        }}
                                    />
                                ) : (
                                    <span style={{ fontSize: '12px', color: '#999' }}>No Photo</span>
                                )}
                            </div>
                            <input
                                type="file"
                                accept=".jpg,.jpeg"
                                onChange={handleImageChange}
                                id="profile-image-upload"
                                style={{ display: 'none' }}
                            />
                            <label
                                htmlFor="profile-image-upload"
                                className="btn-sm"
                                style={{
                                    cursor: 'pointer',
                                    display: 'inline-block',
                                    background: '#f0f0f0',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                    fontSize: '12px'
                                }}
                            >
                                {isEditing ? 'Change Photo' : 'Upload Photo'}
                            </label>
                            <div style={{ fontSize: '10px', color: '#666', marginTop: '4px' }}>JPG/JPEG only</div>
                        </div>
                    </div>

                    <h3 style={{ marginTop: 0, marginBottom: '12px', fontSize: '16px', color: '#666' }}>Basic Information</h3>

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
                            <label>Date of Birth *</label>
                            <input
                                type="date"
                                name="date_of_birth"
                                value={data.date_of_birth}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Gender</label>
                            <select name="gender" value={data.gender} onChange={handleChange}>
                                <option value="">Select...</option>
                                <option value="Male">Male</option>
                                <option value="Female">Female</option>
                                <option value="Other">Other</option>
                            </select>
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Race</label>
                            <input
                                type="text"
                                name="race"
                                value={data.race}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Height (feet)</label>
                            <input
                                type="number"
                                name="height_feet"
                                value={data.height_feet}
                                onChange={handleChange}
                                min={0}
                                max={8}
                            />
                        </div>
                        <div className="form-group">
                            <label>Height (inches)</label>
                            <input
                                type="number"
                                name="height_inches"
                                value={data.height_inches}
                                onChange={handleChange}
                                min={0}
                                max={11}
                            />
                        </div>
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

                    {/* Residence Section - Show for both New and Edit */}
                    <>
                        <hr style={{ margin: '20px 0', border: 'none', borderTop: '1px solid #ddd' }} />
                        <h3 style={{ marginTop: 0, marginBottom: '12px', fontSize: '16px', color: '#666' }}>Current Residence</h3>

                        <div className="form-row">
                            <div className="form-group">
                                <label>Residence Type</label>
                                <select name="residence_type_id" value={residence.residence_type_id || ''} onChange={handleResidenceChange}>
                                    <option value="">Select...</option>
                                    {residenceTypes.map(rt => (
                                        <option key={rt.id} value={rt.id}>{rt.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-group">
                                <label>Established Date</label>
                                <input
                                    type="date"
                                    name="established_date"
                                    value={residence.established_date}
                                    onChange={handleResidenceChange}
                                />
                            </div>
                        </div>

                        <div className="form-row">
                            <div className="form-group" style={{ flex: 1 }}>
                                <label>Address</label>
                                <div style={{ background: '#f9f9f9', padding: '12px', borderRadius: '8px', marginTop: '8px' }}>
                                    <div className="form-row">
                                        <div className="form-group" style={{ flex: 2 }}>
                                            <label>Street *</label>
                                            <input type="text" name="street_line_1" value={newAddress.street_line_1} onChange={handleNewAddressChange} required />
                                        </div>
                                        <div className="form-group" style={{ flex: 1 }}>
                                            <label>Apt/Suite</label>
                                            <input type="text" name="street_line_2" value={newAddress.street_line_2} onChange={handleNewAddressChange} />
                                        </div>
                                    </div>
                                    <div className="form-row">
                                        <div className="form-group">
                                            <label>City *</label>
                                            <input type="text" name="city" value={newAddress.city} onChange={handleNewAddressChange} required />
                                        </div>
                                        <div className="form-group">
                                            <label>State *</label>
                                            <input type="text" name="state_province" value={newAddress.state_province} onChange={handleNewAddressChange} required />
                                        </div>
                                        <div className="form-group">
                                            <label>ZIP *</label>
                                            <input type="text" name="postal_code" value={newAddress.postal_code} onChange={handleNewAddressChange} required />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </>

                    {/* Enrollment Section - Only show for new clients */}
                    {!isEditing && (
                        <>
                            <hr style={{ margin: '20px 0', border: 'none', borderTop: '1px solid #ddd' }} />
                            <h3 style={{ marginTop: 0, marginBottom: '12px', fontSize: '16px', color: '#666' }}>Program Enrollment</h3>

                            <div className="form-row">
                                <div className="form-group" style={{ flex: 1 }}>
                                    <label>
                                        Program Location
                                        <button
                                            type="button"
                                            style={{ marginLeft: '10px', fontSize: '12px' }}
                                            className="btn-sm"
                                            onClick={() => setShowNewLocation(!showNewLocation)}
                                        >
                                            {showNewLocation ? 'Use Existing' : '+ New Location'}
                                        </button>
                                    </label>
                                    {!showNewLocation ? (
                                        <select name="program_location_id" value={enrollment.program_location_id || ''} onChange={handleEnrollmentChange}>
                                            <option value="">Select...</option>
                                            {programLocations.map(pl => (
                                                <option key={pl.id} value={pl.id}>{pl.name}</option>
                                            ))}
                                        </select>
                                    ) : (
                                        <div style={{ background: '#f9f9f9', padding: '12px', borderRadius: '8px', marginTop: '8px' }}>
                                            <div className="form-row">
                                                <div className="form-group" style={{ flex: 2 }}>
                                                    <label>Location Name *</label>
                                                    <input type="text" name="name" value={newLocation.name} onChange={handleNewLocationChange} required />
                                                </div>
                                                <div className="form-group" style={{ flex: 1 }}>
                                                    <label>Type *</label>
                                                    <select name="location_type_id" value={newLocation.location_type_id || ''} onChange={handleNewLocationChange} required>
                                                        <option value="">Select...</option>
                                                        {locationTypes.map(lt => (
                                                            <option key={lt.id} value={lt.id}>{lt.name}</option>
                                                        ))}
                                                    </select>
                                                </div>
                                            </div>
                                            <label>
                                                Address (uses residence address if not set)
                                            </label>
                                            <div style={{ background: '#ffffff', padding: '12px', borderRadius: '8px', marginTop: '8px', border: '1px solid #ddd' }}>
                                                <div className="form-row">
                                                    <div className="form-group" style={{ flex: 2 }}>
                                                        <label>Street *</label>
                                                        <input type="text" name="street_line_1" value={newLocationAddress.street_line_1} onChange={handleNewLocationAddressChange} />
                                                    </div>
                                                    <div className="form-group" style={{ flex: 1 }}>
                                                        <label>Apt/Suite</label>
                                                        <input type="text" name="street_line_2" value={newLocationAddress.street_line_2} onChange={handleNewLocationAddressChange} />
                                                    </div>
                                                </div>
                                                <div className="form-row">
                                                    <div className="form-group">
                                                        <label>City *</label>
                                                        <input type="text" name="city" value={newLocationAddress.city} onChange={handleNewLocationAddressChange} />
                                                    </div>
                                                    <div className="form-group">
                                                        <label>State *</label>
                                                        <input type="text" name="state_province" value={newLocationAddress.state_province} onChange={handleNewLocationAddressChange} />
                                                    </div>
                                                    <div className="form-group">
                                                        <label>ZIP *</label>
                                                        <input type="text" name="postal_code" value={newLocationAddress.postal_code} onChange={handleNewLocationAddressChange} />
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                                <div className="form-group">
                                    <label>Start Date</label>
                                    <input
                                        type="date"
                                        name="start_date"
                                        value={enrollment.start_date}
                                        onChange={handleEnrollmentChange}
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    <div className="form-actions" style={{ marginTop: '24px' }}>
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
