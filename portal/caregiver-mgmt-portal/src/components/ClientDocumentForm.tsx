import { useState } from 'react';

interface Field {
    key: string;
    label: string;
    type: 'text' | 'boolean' | 'date' | 'number';
    conditional?: string;
}

interface Section {
    key: string;
    title: string;
    icon: string;
    fields: Field[];
}

interface FormSchema {
    sections: Section[];
}

interface ClientDocumentFormProps {
    template: {
        id: number;
        name: string;
        description?: string;
        icon: string;
        form_schema: FormSchema;
    };
    existingValues?: Record<string, any>;
    onSave: (values: Record<string, any>) => void;
    onCancel: () => void;
    saving?: boolean;
    readOnly?: boolean;
    documentDetails?: {
        category?: string;
        subcategory?: string;
        templateVersion?: number;
        revisionIntervalDays?: number;
        createdAt?: string;
        createdByName?: string;
        lastReviewedAt?: string;
        lastReviewedBy?: string;
        changesMade?: boolean;
    };
    showBackButton?: boolean;
}

// ... imports and ICON_MAP ...
const ICON_MAP: Record<string, string> = {
    'doc.text': '📄',
    'person': '👤',
    'brain.head.profile': '🧠',
    'heart': '❤️',
    'bolt.heart': '⚡',
    'light.beacon.max': '🚨',
    'checkmark.circle': '✅',
    'clock': '⏰',
    'phone.arrow.up.right': '📞',
    'clock.arrow.circlepath': '🔄',
};

export function ClientDocumentForm({
    template,
    existingValues = {},
    onSave,
    onCancel,
    saving,
    readOnly = false,
    documentDetails,
    showBackButton = false
}: ClientDocumentFormProps) {
    // Values are stored as { sectionKey: { fieldKey: value } }
    const [values, setValues] = useState<Record<string, Record<string, any>>>(existingValues);

    const handleFieldChange = (sectionKey: string, fieldKey: string, value: any) => {
        if (readOnly) return;
        setValues(prev => ({
            ...prev,
            [sectionKey]: {
                ...(prev[sectionKey] || {}),
                [fieldKey]: value
            }
        }));
    };

    // ... getFieldValue, isFieldVisible ...

    const getFieldValue = (sectionKey: string, fieldKey: string): any => {
        return values[sectionKey]?.[fieldKey];
    };

    const isFieldVisible = (sectionKey: string, field: Field): boolean => {
        if (!field.conditional) return true;
        // Check if the conditional field in this section is truthy
        return Boolean(getFieldValue(sectionKey, field.conditional));
    };

    const handleSubmit = () => {
        if (readOnly) return;
        onSave(values);
    };

    return (
        <div className="document-form">
            {/* Back button for history view */}
            {showBackButton && (
                <button
                    className="btn-secondary"
                    onClick={onCancel}
                    style={{ marginBottom: '15px' }}
                >
                    ← Back to Documents
                </button>
            )}
            <div className="form-header">
                <span style={{ fontSize: '32px' }}>{ICON_MAP[template.icon] || '📄'}</span>
                <div>
                    <h3 style={{ margin: 0 }}>{template.name}</h3>
                    {template.description && (
                        <p style={{ margin: '4px 0 0 0', color: '#666', fontSize: '14px' }}>{template.description}</p>
                    )}
                </div>
            </div>

            {/* Document Details Section */}
            {documentDetails && (
                <div style={{
                    background: '#fff',
                    border: '1px solid #dee2e6',
                    borderRadius: '8px',
                    padding: '20px',
                    marginBottom: '20px'
                }}>
                    <h4 style={{ marginTop: 0, marginBottom: '15px', color: '#495057', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>
                        Document Details
                    </h4>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '15px' }}>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Category</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>{documentDetails.category || '—'}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Subcategory</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>{documentDetails.subcategory || '—'}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Template Version</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>v{documentDetails.templateVersion}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Revision Interval</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>{documentDetails.revisionIntervalDays} days</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Created</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>
                                {documentDetails.createdAt
                                    ? new Date(documentDetails.createdAt).toLocaleDateString()
                                    : '—'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Created By</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>{documentDetails.createdByName || '—'}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Last Reviewed</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>
                                {documentDetails.lastReviewedAt
                                    ? new Date(documentDetails.lastReviewedAt).toLocaleDateString()
                                    : '—'}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Reviewed By</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>{documentDetails.lastReviewedBy || '—'}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Changes</div>
                            <div style={{ fontWeight: 500, color: '#333' }}>
                                {documentDetails.changesMade !== undefined
                                    ? (documentDetails.changesMade ? 'Yes' : 'No')
                                    : '—'}
                            </div>
                        </div>
                    </div>
                </div>
            )}
            {template.form_schema?.sections?.map((section) => (
                <div key={section.key} className="form-section">
                    <div className="section-header">
                        <span className="section-icon">{ICON_MAP[section.icon] || '📄'}</span>
                        <h4>{section.title}</h4>
                    </div>
                    <div className="section-fields">
                        {section.fields.map((field) => (
                            isFieldVisible(section.key, field) && (
                                <div key={field.key} className="form-field">
                                    <label htmlFor={`${section.key}-${field.key}`}>{field.label}</label>
                                    {field.type === 'boolean' ? (
                                        <div className="toggle-group">
                                            <button
                                                type="button"
                                                disabled={readOnly}
                                                className={`toggle-btn ${getFieldValue(section.key, field.key) === true ? 'active' : ''}`}
                                                onClick={() => handleFieldChange(section.key, field.key, true)}
                                            >
                                                Yes
                                            </button>
                                            <button
                                                type="button"
                                                disabled={readOnly}
                                                className={`toggle-btn ${getFieldValue(section.key, field.key) === false ? 'active' : ''}`}
                                                onClick={() => handleFieldChange(section.key, field.key, false)}
                                            >
                                                No
                                            </button>
                                        </div>
                                    ) : field.type === 'date' ? (
                                        <input
                                            type="date"
                                            id={`${section.key}-${field.key}`}
                                            value={getFieldValue(section.key, field.key) || ''}
                                            onChange={e => handleFieldChange(section.key, field.key, e.target.value)}
                                            disabled={readOnly}
                                        />
                                    ) : field.type === 'number' ? (
                                        <input
                                            type="number"
                                            id={`${section.key}-${field.key}`}
                                            value={getFieldValue(section.key, field.key) ?? ''}
                                            onChange={e => {
                                                const val = e.target.value;
                                                if (val === '' || val === '-') {
                                                    handleFieldChange(section.key, field.key, val);
                                                } else if (!isNaN(Number(val))) {
                                                    handleFieldChange(section.key, field.key, Number(val));
                                                }
                                            }}
                                            onKeyDown={e => {
                                                // Allow: backspace, delete, tab, escape, enter, arrows, home, end
                                                if ([8, 46, 9, 27, 13, 37, 38, 39, 40, 35, 36].includes(e.keyCode)) return;
                                                // Allow: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
                                                if ((e.ctrlKey || e.metaKey) && [65, 67, 86, 88].includes(e.keyCode)) return;
                                                // Allow: minus sign at start
                                                if (e.key === '-' && e.currentTarget.selectionStart === 0) return;
                                                // Allow: decimal point (once)
                                                if (e.key === '.' && !e.currentTarget.value.includes('.')) return;
                                                // Block non-numeric
                                                if (!/[0-9]/.test(e.key)) e.preventDefault();
                                            }}
                                            inputMode="decimal"
                                            disabled={readOnly}
                                        />
                                    ) : (
                                        <textarea
                                            id={`${section.key}-${field.key}`}
                                            value={getFieldValue(section.key, field.key) || ''}
                                            onChange={e => handleFieldChange(section.key, field.key, e.target.value)}
                                            rows={2}
                                            disabled={readOnly}
                                        />
                                    )}
                                </div>
                            )
                        ))}
                    </div>
                </div>
            ))}

            {/* Hide bottom actions when viewing history or explicitly hidden */}
            {!readOnly && (
                <div className="form-actions">
                    <button type="button" className="btn-secondary" onClick={onCancel}>
                        Cancel
                    </button>
                        <button
                            type="button"
                            className="btn-primary"
                            onClick={handleSubmit}
                            disabled={saving}
                        >
                            {saving ? 'Saving...' : 'Save Document'}
                        </button>
                </div>
            )}

            <style>{`
                .document-form {
                    max-width: 800px;
                }
                .form-header {
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    padding: 20px;
                    background: #f8f9fa;
                    border-radius: 10px;
                    margin-bottom: 20px;
                }
                .form-section {
                    background: #fff;
                    border: 1px solid #e0e0e0;
                    border-radius: 10px;
                    margin-bottom: 16px;
                    overflow: hidden;
                }
                .section-header {
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    padding: 15px 20px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .section-header h4 {
                    margin: 0;
                    font-weight: 600;
                }
                .section-icon {
                    font-size: 20px;
                }
                .section-fields {
                    padding: 20px;
                }
                .form-field {
                    margin-bottom: 16px;
                }
                .form-field:last-child {
                    margin-bottom: 0;
                }
                .form-field label {
                    display: block;
                    font-weight: 500;
                    margin-bottom: 6px;
                    color: #333;
                }
                .form-field input,
                .form-field textarea {
                    width: 100%;
                    padding: 10px 12px;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    font-size: 14px;
                    transition: border-color 0.2s;
                }
                .form-field input:focus,
                .form-field textarea:focus {
                    outline: none;
                    border-color: #667eea;
                    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
                }
                .toggle-group {
                    display: flex;
                    gap: 0;
                    border-radius: 6px;
                    overflow: hidden;
                    border: 1px solid #ddd;
                    width: fit-content;
                }
                .toggle-btn {
                    padding: 8px 24px;
                    border: none;
                    background: #f5f5f5;
                    cursor: pointer;
                    font-size: 14px;
                    transition: all 0.2s;
                }
                .toggle-btn:first-child {
                    border-right: 1px solid #ddd;
                }
                .toggle-btn.active {
                    background: #667eea;
                    color: white;
                }
                .toggle-btn:hover:not(.active) {
                    background: #e8e8e8;
                }
            `}</style>
        </div>
    );
}
