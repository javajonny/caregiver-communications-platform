import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface ResidenceFormData {
    residence_type_id: number | null;
    address_id: number | null;
    start_date: string;
}

interface NewAddressData {
    street_line_1: string;
    street_line_2: string;
    city: string;
    state_province: string;
    postal_code: string;
    country: string;
}

interface ResidenceFormProps {
    clientId: number;
    initialData?: ResidenceFormData;
    hasExisting: boolean;
    residenceId?: number;
    onSubmit: () => void;
    onCancel: () => void;
}

interface ResidenceType {
    id: number;
    name: string;
}

const defaultData: ResidenceFormData = {
    residence_type_id: null,
    address_id: null,
    start_date: new Date().toISOString().split('T')[0],
};

const defaultNewAddress: NewAddressData = {
    street_line_1: '',
    street_line_2: '',
    city: '',
    state_province: '',
    postal_code: '',
    country: 'USA',
};

export function ResidenceForm({ clientId, initialData, hasExisting, residenceId, onSubmit, onCancel }: ResidenceFormProps) {
    const [data, setData] = useState<ResidenceFormData>(initialData || defaultData);
    const [residenceTypes, setResidenceTypes] = useState<ResidenceType[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const [newAddress, setNewAddress] = useState<NewAddressData>(defaultNewAddress);

    useEffect(() => {
        Promise.all([
            api.getResidenceTypes(),
        ]).then(([resTypes]) => {
            setResidenceTypes(resTypes);
        }).catch(console.error);
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value } = e.target;
        setData(prev => ({
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
            // Always create new address
            let addressId = data.address_id;
            if (newAddress.street_line_1) {
                const createdAddress = await api.createAddress(newAddress);
                addressId = createdAddress.id;
            }

            const residenceData = {
                residence_type_id: data.residence_type_id,
                address_id: addressId,
                start_date: data.start_date,
            };

            if (hasExisting && residenceId) {
                await api.updateClientResidence(clientId, residenceId, residenceData);
            } else {
                await api.createClientResidence({ client_id: clientId, ...residenceData });
            }
            onSubmit();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save residence');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px', maxHeight: '90vh', overflowY: 'auto' }}>
                <h2>{hasExisting ? 'Edit Residence' : 'Set Residence'}</h2>

                {error && <div className="error-message">{error}</div>}

                <form onSubmit={handleSubmit}>
                    <div className="form-row">
                        <div className="form-group" style={{ flex: 1 }}>
                            <label>Residence Type *</label>
                            <select
                                name="residence_type_id"
                                value={data.residence_type_id || ''}
                                onChange={handleChange}
                                required
                            >
                                <option value="">Select...</option>
                                {residenceTypes.map(rt => (
                                    <option key={rt.id} value={rt.id}>{rt.name}</option>
                                ))}
                            </select>
                        </div>
                        <div className="form-group">
                            <label>Start Date</label>
                            <input
                                type="date"
                                name="start_date"
                                value={data.start_date}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Address *</label>
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

                    <div className="form-actions">
                        <button type="button" className="btn-secondary" onClick={onCancel}>
                            Cancel
                        </button>
                        <button type="submit" className="btn-primary" disabled={loading}>
                            {loading ? 'Saving...' : hasExisting ? 'Update' : 'Save'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
