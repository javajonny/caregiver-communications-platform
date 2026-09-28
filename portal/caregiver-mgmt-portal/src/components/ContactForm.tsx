import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface ContactFormData {
    contact_first_name: string;
    contact_last_name: string;
    contact_phone_primary: string;
    contact_phone_secondary?: string;
    contact_email?: string;
    relationship: number | null;
    is_primary: boolean;
    address_id?: number | null;
    address?: NewAddressData; // Added to receive nested address from API
}

interface NewAddressData {
    street_line_1: string;
    street_line_2: string;
    city: string;
    state_province: string;
    postal_code: string;
    country: string;
}

interface ContactFormProps {
    clientId: number;
    initialData?: ContactFormData & { id?: number };
    onSubmit: () => void;
    onCancel: () => void;
    isEditing?: boolean;
}

interface RelationshipType {
    id: number;
    name: string;
}


const defaultData: ContactFormData = {
    contact_first_name: '',
    contact_last_name: '',
    contact_phone_primary: '',
    contact_phone_secondary: '',
    contact_email: '',
    relationship: null,
    is_primary: false,
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

export function ContactForm({ clientId, initialData, onSubmit, onCancel, isEditing }: ContactFormProps) {
    const [data, setData] = useState<ContactFormData>(initialData || defaultData);
    const [relationshipTypes, setRelationshipTypes] = useState<RelationshipType[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Initialize address state from initialData.address if available
    const [newAddress, setNewAddress] = useState<NewAddressData>(() => {
        if (initialData?.address) {
            return {
                street_line_1: initialData.address.street_line_1 || '',
                street_line_2: initialData.address.street_line_2 || '',
                city: initialData.address.city || '',
                state_province: initialData.address.state_province || '',
                postal_code: initialData.address.postal_code || '',
                country: initialData.address.country || 'USA',
            };
        }
        return defaultNewAddress;
    });

    useEffect(() => {
        Promise.all([
            api.getRelationshipTypes(),
        ]).then(([types]) => {
            setRelationshipTypes(types);
        }).catch(console.error);
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value, type } = e.target;
        setData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked :
                (name === 'relationship' || name === 'address_id') ? (value ? Number(value) : null) : value
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
            let addressId = data.address_id;

            // Create new address if needed
            if (newAddress.street_line_1) {
                const createdAddress = await api.createAddress(newAddress);
                addressId = createdAddress.id;
            }

            const submitData = { ...data, address_id: addressId };

            if (isEditing && initialData?.id) {
                await api.updateClientContact(initialData.id, submitData);
            } else {
                await api.createClientContact({ client_id: clientId, ...submitData });
            }
            onSubmit();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to save contact');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '800px' }}>
                <h2>{isEditing ? 'Edit Contact' : 'Add Contact'}</h2>

                {error && <div className="error-message">{error}</div>}

                <form onSubmit={handleSubmit}>
                    <div className="form-row">
                        <div className="form-group">
                            <label>First Name *</label>
                            <input
                                type="text"
                                name="contact_first_name"
                                value={data.contact_first_name}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Last Name *</label>
                            <input
                                type="text"
                                name="contact_last_name"
                                value={data.contact_last_name}
                                onChange={handleChange}
                                required
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Phone *</label>
                            <input
                                type="tel"
                                name="contact_phone_primary"
                                value={data.contact_phone_primary}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>Alt Phone</label>
                            <input
                                type="tel"
                                name="contact_phone_secondary"
                                value={data.contact_phone_secondary || ''}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group" style={{ flex: 1 }}>
                            <label>Email</label>
                            <input
                                type="email"
                                name="contact_email"
                                value={data.contact_email || ''}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group" style={{ flex: 1 }}>
                            <label>Relationship *</label>
                            <select name="relationship" value={data.relationship || ''} onChange={handleChange} required>
                                <option value="">Select...</option>
                                {relationshipTypes.map(rt => (
                                    <option key={rt.id} value={rt.id}>{rt.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Address (Optional)</label>
                        <div style={{ background: '#f9f9f9', padding: '12px', borderRadius: '8px', marginTop: '8px' }}>
                            <div className="form-row">
                                <div className="form-group" style={{ flex: 2 }}>
                                    <label>Street *</label>
                                    <input type="text" name="street_line_1" value={newAddress.street_line_1} onChange={handleNewAddressChange} required={!!newAddress.street_line_1} />
                                </div>
                                <div className="form-group" style={{ flex: 1 }}>
                                    <label>Apt/Suite</label>
                                    <input type="text" name="street_line_2" value={newAddress.street_line_2} onChange={handleNewAddressChange} />
                                </div>
                            </div>
                            <div className="form-row">
                                <div className="form-group">
                                    <label>City *</label>
                                    <input type="text" name="city" value={newAddress.city} onChange={handleNewAddressChange} required={!!newAddress.street_line_1} />
                                </div>
                                <div className="form-group">
                                    <label>State *</label>
                                    <input type="text" name="state_province" value={newAddress.state_province} onChange={handleNewAddressChange} required={!!newAddress.street_line_1} />
                                </div>
                                <div className="form-group">
                                    <label>ZIP *</label>
                                    <input type="text" name="postal_code" value={newAddress.postal_code} onChange={handleNewAddressChange} required={!!newAddress.street_line_1} />
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group checkbox-group">
                            <input
                                type="checkbox"
                                name="is_primary"
                                checked={data.is_primary}
                                onChange={handleChange}
                            />
                            <label>Primary Contact</label>
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
