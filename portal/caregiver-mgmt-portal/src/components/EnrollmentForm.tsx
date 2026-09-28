import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface EnrollmentFormData {
    program_location_id: number | null;
    start_date: string;
    end_date: string | null;
}

interface NewLocationData {
    name: string;
    location_type_id: number | null;
    address_id: number | null;
}

interface NewAddressData {
    street_line_1: string;
    street_line_2: string;
    city: string;
    state_province: string;
    postal_code: string;
    country: string;
}

interface EnrollmentFormProps {
    clientId: number;
    initialData?: EnrollmentFormData & { id?: number };
    onSubmit: () => void;
    onCancel: () => void;
    isEditing?: boolean;
}

interface ProgramLocation {
    id: number;
    name: string;
    location_type: LocationType;
}

interface LocationType {
    id: number;
    name: string;
}


const defaultData: EnrollmentFormData = {
    program_location_id: null,
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
};

const defaultNewLocation: NewLocationData = {
    name: '',
    location_type_id: null,
    address_id: null,
};

const defaultNewAddress: NewAddressData = {
    street_line_1: '',
    street_line_2: '',
    city: '',
    state_province: '',
    postal_code: '',
    country: 'USA',
};

export function EnrollmentForm({ clientId, onSubmit, onCancel }: EnrollmentFormProps) {
    const [data, setData] = useState<EnrollmentFormData>(defaultData);
    const [locations, setLocations] = useState<ProgramLocation[]>([]);
    const [locationTypes, setLocationTypes] = useState<LocationType[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const [showNewLocation, setShowNewLocation] = useState(false);
    const [newLocation, setNewLocation] = useState<NewLocationData>(defaultNewLocation);
    const [newAddress, setNewAddress] = useState<NewAddressData>(defaultNewAddress);

    useEffect(() => {
        Promise.all([
            api.getLocations(),
            api.getLocationTypes(),
        ]).then(([locs, types]) => {
            setLocations(locs);
            setLocationTypes(types);
        }).catch(console.error);
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setData(prev => ({
            ...prev,
            [name]: name === 'program_location_id' ? (value ? Number(value) : null) : value
        }));
    };

    const handleNewLocationChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setNewLocation(prev => ({
            ...prev,
            [name]: name.endsWith('_id') ? (value ? Number(value) : null) : value
        }));
    };

    const handleNewAddressChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setNewAddress(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            let locationId = data.program_location_id;

            // Validation for new location mode
            if (showNewLocation) {
                if (!newLocation.name) {
                    setError('Please enter a location name');
                    setLoading(false);
                    return;
                }
                if (!newLocation.location_type_id) {
                    setError('Please select a location type');
                    setLoading(false);
                    return;
                }

                // Create new address
                if (!newAddress.street_line_1) {
                    setError('Please enter a street address');
                    setLoading(false);
                    return;
                }
                const createdAddress = await api.createAddress(newAddress);
                const addressId = createdAddress.id;

                const createdLocation = await api.createProgramLocation({
                    name: newLocation.name,
                    location_type_id: newLocation.location_type_id,
                    address_id: addressId,
                });
                locationId = createdLocation.id;
            } else if (!data.program_location_id) {
                setError('Please select a program location');
                setLoading(false);
                return;
            }

            const submitData = {
                ...data,
                program_location_id: locationId,
                end_date: null, // New enrollments are always active
            };

            await api.createClientEnrollment({ client_id: clientId, ...submitData });
            onSubmit();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save enrollment');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '800px' }}>
                <h2>Add Enrollment</h2>

                {error && <div className="error-message">{error}</div>}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>
                            Program Location *
                            <button
                                type="button"
                                style={{ marginLeft: '10px', fontSize: '12px' }}
                                className="btn-sm"
                                onClick={() => {
                                    setShowNewLocation(!showNewLocation);
                                }}
                            >
                                {showNewLocation ? 'Use Existing' : '+ New Location'}
                            </button>
                        </label>

                        {!showNewLocation ? (
                            <select
                                name="program_location_id"
                                value={data.program_location_id || ''}
                                onChange={handleChange}
                                required
                            >
                                <option value="">Select Location...</option>
                                {locations.map(loc => (
                                    <option key={loc.id} value={loc.id}>{loc.name}</option>
                                ))}
                            </select>
                        ) : (
                            <div style={{ background: '#f9f9f9', padding: '12px', borderRadius: '8px', marginTop: '8px' }}>
                                <div className="form-group">
                                    <label>Location Name *</label>
                                    <input
                                        type="text"
                                        name="name"
                                        value={newLocation.name}
                                        onChange={handleNewLocationChange}
                                        required
                                        placeholder="e.g., Oak Street Home"
                                    />
                                </div>

                                <div className="form-group">
                                    <label>Location Type *</label>
                                    <select
                                        name="location_type_id"
                                        value={newLocation.location_type_id || ''}
                                        onChange={handleNewLocationChange}
                                        required
                                    >
                                        <option value="">Select Type...</option>
                                        {locationTypes.map(lt => (
                                            <option key={lt.id} value={lt.id}>{lt.name}</option>
                                        ))}
                                    </select>
                                </div>

                                <div className="form-group">
                                    <label>Address *</label>
                                    <div style={{ background: '#fff', padding: '10px', borderRadius: '6px', marginTop: '8px', border: '1px solid #ddd' }}>
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
                        )}
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Start Date *</label>
                            <input
                                type="date"
                                name="start_date"
                                value={data.start_date}
                                onChange={handleChange}
                                required
                            />
                        </div>
                    </div>

                    <div className="form-actions">
                        <button type="button" className="btn-secondary" onClick={onCancel}>
                            Cancel
                        </button>
                        <button type="submit" className="btn-primary" disabled={loading}>
                            {loading ? 'Saving...' : 'Create'}
                        </button>
                    </div>
                </form>
            </div >
        </div >
    );
}
