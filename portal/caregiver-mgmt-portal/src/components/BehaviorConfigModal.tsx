import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { usePermission } from '../hooks/usePermission';

interface BehaviorType {
    id: number;
    name: string;
    description?: string;
}

interface BehaviorConfigItem {
    id: number;
    behavior_type_id: number;
    target_value?: number;
    notes?: string;
}

interface BehaviorConfigVersion {
    id: number;
    client_id: number;
    version: number;
    is_active: boolean;
    created_at: string;
    created_by?: number;
    notes?: string;
    items: BehaviorConfigItem[];
}

interface BehaviorConfigModalProps {
    clientId: number;
    onSubmit: () => void;
    onCancel: () => void;
}

export function BehaviorConfigModal({ clientId, onSubmit, onCancel }: BehaviorConfigModalProps) {
    const [behaviorTypes, setBehaviorTypes] = useState<BehaviorType[]>([]);
    const [currentConfigVersion, setCurrentConfigVersion] = useState<BehaviorConfigVersion | null>(null);
    const [selectedBehaviorIds, setSelectedBehaviorIds] = useState<number[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // New behavior type form state
    const [showNewBehaviorForm, setShowNewBehaviorForm] = useState(false);
    const [newBehaviorName, setNewBehaviorName] = useState('');
    const [newBehaviorDescription, setNewBehaviorDescription] = useState('');
    const [creatingBehavior, setCreatingBehavior] = useState(false);

    const { canCreate } = usePermission();
    const canCreateBehaviorType = canCreate('behavior_types'); // Admin/Director only

    useEffect(() => {
        loadData();
    }, [clientId]);

    const loadData = () => {
        Promise.all([
            api.getBehaviorTypes(),
            api.getClientBehaviorConfigs(clientId)
        ]).then(([types, configs]) => {
            setBehaviorTypes(types);
            // Find active config version
            const activeConfig = configs.find((c: BehaviorConfigVersion) => c.is_active);
            if (activeConfig) {
                setCurrentConfigVersion(activeConfig);
                setSelectedBehaviorIds(activeConfig.items.map((item: BehaviorConfigItem) => item.behavior_type_id));
            }
        }).catch(err => {
            console.error('Error loading behavior config data:', err);
            setError('Failed to load behavior types');
        });
    };

    const toggleBehaviorSelection = (typeId: number) => {
        setSelectedBehaviorIds(prev =>
            prev.includes(typeId)
                ? prev.filter(id => id !== typeId)
                : [...prev, typeId]
        );
    };

    const handleCreateBehaviorType = async () => {
        if (!newBehaviorName.trim()) {
            setError('Please enter a behavior name');
            return;
        }

        setCreatingBehavior(true);
        setError('');

        try {
            const newType = await api.createBehaviorType({
                name: newBehaviorName.trim(),
                description: newBehaviorDescription.trim() || undefined
            });

            // Add to list and auto-select
            setBehaviorTypes(prev => [...prev, newType]);
            setSelectedBehaviorIds(prev => [...prev, newType.id]);

            // Reset form
            setNewBehaviorName('');
            setNewBehaviorDescription('');
            setShowNewBehaviorForm(false);
        } catch (err) {
            console.error('Error creating behavior type:', err);
            setError(err instanceof Error ? err.message : 'Failed to create behavior type');
        } finally {
            setCreatingBehavior(false);
        }
    };

    const handleSave = async () => {
        if (selectedBehaviorIds.length === 0) {
            setError('Please select at least one behavior to track');
            return;
        }

        setLoading(true);
        setError('');

        try {
            await api.createClientBehaviorConfig(clientId, {
                behavior_type_ids: selectedBehaviorIds,
                notes: `Updated from portal on ${new Date().toLocaleDateString()}`
            });
            onSubmit();
        } catch (err) {
            console.error('Error saving behavior config:', err);
            setError(err instanceof Error ? err.message : 'Failed to save configuration');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onCancel}>
            <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '550px' }}>
                <h2>Manage Tracked Behaviors</h2>

                {error && <div className="error-message">{error}</div>}

                {currentConfigVersion && (
                    <p style={{ fontSize: '12px', color: '#666', marginBottom: '16px' }}>
                        Current config: Version {currentConfigVersion.version} {' '}
                        (created {new Date(currentConfigVersion.created_at).toLocaleDateString()})
                    </p>
                )}

                <p style={{ marginBottom: '12px', color: 'var(--text-muted)' }}>
                    Select which behaviors to track for this client. Saving will create a new version.
                </p>

                {/* Create New Behavior Type (Admin/Director only) */}
                {canCreateBehaviorType && (
                    <div style={{ marginBottom: '16px' }}>
                        {!showNewBehaviorForm ? (
                            <button
                                type="button"
                                className="btn-sm"
                                onClick={() => setShowNewBehaviorForm(true)}
                                style={{ fontSize: '12px' }}
                            >
                                + Create New Behavior Type
                            </button>
                        ) : (
                            <div style={{
                                background: 'var(--bg-secondary, #f5f5f5)',
                                padding: '12px',
                                borderRadius: '8px',
                                border: '1px solid var(--border, #ddd)'
                            }}>
                                <div style={{ marginBottom: '8px' }}>
                                    <input
                                        type="text"
                                        placeholder="Behavior name *"
                                        value={newBehaviorName}
                                        onChange={e => setNewBehaviorName(e.target.value)}
                                        style={{ width: '100%', marginBottom: '8px' }}
                                    />
                                    <input
                                        type="text"
                                        placeholder="Description (optional)"
                                        value={newBehaviorDescription}
                                        onChange={e => setNewBehaviorDescription(e.target.value)}
                                        style={{ width: '100%' }}
                                    />
                                </div>
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <button
                                        type="button"
                                        className="btn-sm btn-primary"
                                        onClick={handleCreateBehaviorType}
                                        disabled={creatingBehavior || !newBehaviorName.trim()}
                                    >
                                        {creatingBehavior ? 'Creating...' : 'Create'}
                                    </button>
                                    <button
                                        type="button"
                                        className="btn-sm btn-secondary"
                                        onClick={() => {
                                            setShowNewBehaviorForm(false);
                                            setNewBehaviorName('');
                                            setNewBehaviorDescription('');
                                        }}
                                    >
                                        Cancel
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px', maxHeight: '300px', overflowY: 'auto' }}>
                    {behaviorTypes.map(type => (
                        <label
                            key={type.id}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '8px 12px',
                                background: selectedBehaviorIds.includes(type.id) ? '#e3f2fd' : '#f5f5f5',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                border: selectedBehaviorIds.includes(type.id) ? '1px solid #1976d2' : '1px solid #ddd'
                            }}
                        >
                            <input
                                type="checkbox"
                                checked={selectedBehaviorIds.includes(type.id)}
                                onChange={() => toggleBehaviorSelection(type.id)}
                            />
                            <span style={{ fontWeight: selectedBehaviorIds.includes(type.id) ? 500 : 400 }}>
                                {type.name}
                            </span>
                            {type.description && (
                                <span style={{ fontSize: '12px', color: '#666', marginLeft: 'auto' }}>
                                    {type.description}
                                </span>
                            )}
                        </label>
                    ))}
                </div>

                {behaviorTypes.length === 0 && !error && (
                    <p className="text-muted">Loading behavior types...</p>
                )}

                <div className="form-actions">
                    <button type="button" className="btn-secondary" onClick={onCancel}>
                        Cancel
                    </button>
                    <button
                        type="button"
                        className="btn-primary"
                        onClick={handleSave}
                        disabled={loading || selectedBehaviorIds.length === 0}
                    >
                        {loading ? 'Saving...' : 'Save Configuration'}
                    </button>
                </div>
            </div>
        </div>
    );
}

