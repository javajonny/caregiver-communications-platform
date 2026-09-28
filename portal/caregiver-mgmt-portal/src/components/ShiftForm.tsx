import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface ShiftFormData {
    shift_template_id: number | null;
    program_location_id: number;
    shift_date: string;
    start_time: string;
    end_time: string;
}

interface ShiftTemplate {
    id: number;
    name: string;
    program_location_id: number;
    start_time: string;
    end_time: string;
}

interface Location {
    id: number;
    name: string;
}

interface ShiftFormProps {
    onSubmit: (data: ShiftFormData) => Promise<void>;
    onCancel: () => void;
    initialData?: ShiftFormData; // For editing
}

export function ShiftForm({ onSubmit, onCancel, initialData }: ShiftFormProps) {
    const [locations, setLocations] = useState<Location[]>([]);
    const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const [data, setData] = useState<ShiftFormData>(initialData || {
        shift_template_id: null,
        program_location_id: 0,
        shift_date: new Date().toISOString().split('T')[0],
        start_time: '',
        end_time: '',
    });

    useEffect(() => {
        // Fetch locations and templates
        Promise.all([
            api.getLocations(),
            api.getShiftTemplates()
        ]).then(([locs, temps]) => {
            setLocations(locs);
            setTemplates(temps);

            // If creating new shift and only one location (e.g. Site Director), select it
            if (!initialData && locs.length === 1) {
                setData(prev => ({ ...prev, program_location_id: locs[0].id }));
            }
        }).catch(err => {
            console.error(err);
            setError('Failed to load form data');
        });
    }, [initialData]);

    const handleLocationChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const locationId = Number(e.target.value);
        setData(prev => ({
            ...prev,
            program_location_id: locationId,
            shift_template_id: null, // Reset template when location changes
            start_time: '',
            end_time: ''
        }));
    };

    const handleTemplateChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
        const templateId = Number(e.target.value);
        const template = templates.find(t => t.id === templateId);

        if (template) {
            setData(prev => ({
                ...prev,
                shift_template_id: templateId,
                program_location_id: template.program_location_id,
                start_time: template.start_time,
                end_time: template.end_time
            }));
        } else {
            setData(prev => ({
                ...prev,
                shift_template_id: null
            }));
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setData(prev => ({ ...prev, [name]: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError('');

        try {
            await onSubmit(data);
        } catch (err: any) {
            setError(err.message || 'Failed to change shift');
        } finally {
            setLoading(false);
        }
    };

    // Filter templates by selected location
    const availableTemplates = templates.filter(
        t => !data.program_location_id || t.program_location_id === data.program_location_id
    );

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()}>
                <h2>Edit Shift</h2>

                {error && <div className="error-message">{error}</div>}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label>Location *</label>
                        <select
                            name="program_location_id"
                            value={data.program_location_id || ''}
                            onChange={handleLocationChange}
                            required
                        >
                            <option value="">Select Location</option>
                            {locations.map(loc => (
                                <option key={loc.id} value={loc.id}>{loc.name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Template *</label>
                        <select
                            name="shift_template_id"
                            value={data.shift_template_id || ''}
                            onChange={handleTemplateChange}
                        >
                            <option value="">Custom Shift (No Template)</option>
                            {availableTemplates.map(temp => (
                                <option key={temp.id} value={temp.id}>{temp.name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="form-group">
                        <label>Date *</label>
                        <input
                            type="date"
                            name="shift_date"
                            value={data.shift_date}
                            onChange={handleChange}
                            required
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Start Time *</label>
                            <input
                                type="time"
                                name="start_time"
                                value={data.start_time}
                                onChange={handleChange}
                                required
                            />
                        </div>
                        <div className="form-group">
                            <label>End Time *</label>
                            <input
                                type="time"
                                name="end_time"
                                value={data.end_time}
                                onChange={handleChange}
                                required
                            />
                        </div>
                    </div>

                    <div className="form-actions">
                        <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
                        <button type="submit" className="btn-primary" disabled={loading}>
                            {loading ? 'Changing...' : 'Change Shift'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
