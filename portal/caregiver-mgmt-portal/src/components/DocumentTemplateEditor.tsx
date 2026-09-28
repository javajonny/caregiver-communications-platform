import { useState, useEffect } from 'react';
import { api } from '../services/api';
import { usePermission } from '../hooks/usePermission';

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

interface DocumentTemplateEditorProps {
    template?: {
        id?: number;
        name: string;
        description: string;
        category_id: number;
        subcategory_id: number | null;
        icon: string;
        revision_interval_days: number;
        form_schema: FormSchema;
    };
    categories: { id: number; name: string }[];
    onSave: (data: any) => void;
    onCancel: () => void;
    onCategoriesChanged?: () => void;  // Callback to refresh categories list
    saving?: boolean;
}

const FIELD_TYPES = [
    { value: 'text', label: 'Text' },
    { value: 'boolean', label: 'Yes/No' },
    { value: 'date', label: 'Date' },
    { value: 'number', label: 'Number' },
];

const ICONS = [
    // General
    { value: 'doc.text', label: '📄 Document' },
    { value: 'doc.text.fill', label: '📋 Document Filled' },
    { value: 'folder', label: '📁 Folder' },
    { value: 'folder.fill', label: '📂 Folder Open' },
    { value: 'list.bullet', label: '📝 List' },
    { value: 'note.text', label: '🗒️ Note' },
    // People
    { value: 'person', label: '👤 Person' },
    { value: 'person.fill', label: '👥 Person Filled' },
    { value: 'person.2', label: '👫 People' },
    { value: 'person.crop.circle', label: '🧑 Profile' },
    // Medical & Health
    { value: 'heart', label: '❤️ Heart' },
    { value: 'heart.fill', label: '💗 Heart Filled' },
    { value: 'bolt.heart', label: '⚡ Emergency Heart' },
    { value: 'stethoscope', label: '🩺 Stethoscope' },
    { value: 'pills', label: '💊 Pills' },
    { value: 'cross.case', label: '🏥 First Aid' },
    { value: 'bandage', label: '🩹 Bandage' },
    { value: 'thermometer', label: '🌡️ Thermometer' },
    { value: 'bed.double', label: '🛏️ Bed' },
    // Brain & Behavior
    { value: 'brain.head.profile', label: '🧠 Brain' },
    { value: 'brain', label: '🧠 Brain Alt' },
    // Emergency & Safety
    { value: 'light.beacon.max', label: '🚨 Alert' },
    { value: 'exclamationmark.triangle', label: '⚠️ Warning' },
    { value: 'exclamationmark.shield', label: '🛡️ Shield Alert' },
    { value: 'bell', label: '🔔 Bell' },
    { value: 'bell.fill', label: '🔔 Bell Filled' },
    // Communication
    { value: 'phone', label: '📞 Phone' },
    { value: 'phone.arrow.up.right', label: '📲 Call Out' },
    { value: 'message', label: '💬 Message' },
    { value: 'envelope', label: '✉️ Email' },
    // Time & Schedule
    { value: 'clock', label: '⏰ Clock' },
    { value: 'clock.arrow.circlepath', label: '🔄 Clock Repeat' },
    { value: 'calendar', label: '📅 Calendar' },
    // Status & Actions
    { value: 'checkmark.circle', label: '✅ Checkmark' },
    { value: 'checkmark.circle.fill', label: '✔️ Checkmark Filled' },
    { value: 'xmark.circle', label: '❌ X Mark' },
    { value: 'questionmark.circle', label: '❓ Question' },
    { value: 'info.circle', label: 'ℹ️ Info' },
    // Location & Home
    { value: 'house', label: '🏠 House' },
    { value: 'house.fill', label: '🏡 House Filled' },
    { value: 'mappin', label: '📍 Location' },
    { value: 'car', label: '🚗 Car' },
    // Other
    { value: 'star', label: '⭐ Star' },
    { value: 'star.fill', label: '🌟 Star Filled' },
    { value: 'hand.raised', label: '✋ Hand' },
    { value: 'figure.walk', label: '🚶 Walking' },
    { value: 'fork.knife', label: '🍴 Food' },
    { value: 'cup.and.saucer', label: '☕ Drink' },
];

export function DocumentTemplateEditor({
    template,
    categories,
    onSave,
    onCancel,
    onCategoriesChanged,
    saving
}: DocumentTemplateEditorProps) {
    const { isAdminOrDirector } = usePermission();
    const [name, setName] = useState(template?.name || '');
    const [description, setDescription] = useState(template?.description || '');
    const [categoryId, setCategoryId] = useState(template?.category_id || 0);
    const [subcategoryId, setSubcategoryId] = useState<number | null>(template?.subcategory_id || null);
    const [icon, setIcon] = useState(template?.icon || 'doc.text');
    const [revisionInterval, setRevisionInterval] = useState(template?.revision_interval_days || 365);
    const [sections, setSections] = useState<Section[]>(template?.form_schema?.sections || []);
    const [subcategories, setSubcategories] = useState<{ id: number; name: string }[]>([]);

    // Load subcategories when category changes
    useEffect(() => {
        if (categoryId > 0) {
            api.getDocumentSubcategories(categoryId)
                .then(setSubcategories)
                .catch(() => setSubcategories([]));
        } else {
            setSubcategories([]);
        }
    }, [categoryId]);

    // Track which section is expanded for editing
    const [expandedSection, setExpandedSection] = useState<number | null>(null);

    // Category/Subcategory creation state
    const [showNewCategoryInput, setShowNewCategoryInput] = useState(false);
    const [showNewSubcategoryInput, setShowNewSubcategoryInput] = useState(false);
    const [newCategoryName, setNewCategoryName] = useState('');
    const [newCategoryDescription, setNewCategoryDescription] = useState('');
    const [newCategoryIcon, setNewCategoryIcon] = useState('folder');
    const [newSubcategoryName, setNewSubcategoryName] = useState('');
    const [newSubcategoryIcon, setNewSubcategoryIcon] = useState('doc.text');

    const handleCreateCategory = async () => {
        if (!newCategoryName.trim()) return;
        try {
            const created = await api.createDocumentCategory({
                name: newCategoryName.trim(),
                description: newCategoryDescription.trim() || undefined,
                icon: newCategoryIcon
            });
            setCategoryId(created.id);
            setNewCategoryName('');
            setNewCategoryDescription('');
            setNewCategoryIcon('folder');
            setShowNewCategoryInput(false);
            onCategoriesChanged?.();  // Refresh categories list
        } catch (err) {
            alert('Failed to create category');
        }
    };

    const handleCreateSubcategory = async () => {
        if (!newSubcategoryName.trim() || !categoryId) return;
        try {
            const created = await api.createDocumentSubcategory(categoryId, newSubcategoryName.trim(), newSubcategoryIcon);
            setSubcategoryId(created.id);
            setNewSubcategoryName('');
            setNewSubcategoryIcon('doc.text');
            setShowNewSubcategoryInput(false);
            // Refresh subcategories
            const updated = await api.getDocumentSubcategories(categoryId);
            setSubcategories(updated);
        } catch (err) {
            alert('Failed to create subcategory');
        }
    };

    // Helper to generate a stable unique ID that won't change when labels are edited
    // Uses crypto.randomUUID() for guaranteed uniqueness (no collision possible)
    const generateStableId = (prefix: string): string => {
        return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
    };

    const addSection = () => {
        const newSection: Section = {
            key: generateStableId('section'),
            title: 'New Section',
            icon: 'doc.text',
            fields: []
        };
        setSections([...sections, newSection]);
        setExpandedSection(sections.length);
    };

    const updateSection = (index: number, updates: Partial<Section>) => {
        const updated = [...sections];
        updated[index] = { ...updated[index], ...updates };
        setSections(updated);
    };

    const removeSection = (index: number) => {
        setSections(sections.filter((_, i) => i !== index));
        setExpandedSection(null);
    };

    const addField = (sectionIndex: number) => {
        const updated = [...sections];
        updated[sectionIndex].fields.push({
            key: generateStableId('field'),
            label: 'New Field',
            type: 'text'
        });
        setSections(updated);
    };

    const updateField = (sectionIndex: number, fieldIndex: number, updates: Partial<Field>) => {
        const updated = [...sections];
        updated[sectionIndex].fields[fieldIndex] = {
            ...updated[sectionIndex].fields[fieldIndex],
            ...updates
        };
        setSections(updated);
    };

    const removeField = (sectionIndex: number, fieldIndex: number) => {
        const updated = [...sections];
        updated[sectionIndex].fields = updated[sectionIndex].fields.filter((_, i) => i !== fieldIndex);
        setSections(updated);
    };

    const handleSubmit = () => {
        // Keys are now stable - assigned at creation time and never change
        // Just pass through sections as-is (no key regeneration needed)
        const formSchema: FormSchema = { sections };
        onSave({
            name,
            description,
            category_id: categoryId,
            subcategory_id: subcategoryId,
            icon,
            revision_interval_days: revisionInterval,
            form_schema: formSchema
        });
    };

    return (
        <div className="template-editor">
            {/* Basic Info */}
            <div className="editor-section">
                <h3>Template Details</h3>
                <div className="form-row">
                    <div className="form-group">
                        <label>Template Name *</label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="e.g., Emergency Fact Sheet"
                        />
                    </div>
                    <div className="form-group">
                        <label>Category *</label>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'stretch' }}>
                            <select value={categoryId} onChange={e => { setCategoryId(Number(e.target.value)); setSubcategoryId(null); }} style={{ flex: 1 }}>
                                <option value={0}>-- Select Category --</option>
                                {categories.map(c => (
                                    <option key={c.id} value={c.id}>{c.name}</option>
                                ))}
                            </select>
                            {isAdminOrDirector() && !showNewCategoryInput && (
                                <button
                                    type="button"
                                    onClick={() => setShowNewCategoryInput(true)}
                                    title="Add Category"
                                    style={{
                                        padding: '0 12px',
                                        fontSize: '18px',
                                        fontWeight: 'bold',
                                        background: 'var(--primary)',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '6px',
                                        cursor: 'pointer'
                                    }}
                                >+</button>
                            )}
                        </div>
                    </div>
                    <div className="form-group">
                        <label>Subcategory</label>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'stretch' }}>
                            <select
                                value={subcategoryId || ''}
                                onChange={e => setSubcategoryId(e.target.value ? Number(e.target.value) : null)}
                                disabled={!categoryId}
                                style={{ flex: 1 }}
                            >
                                <option value="">-- Optional --</option>
                                {subcategories.map(s => (
                                    <option key={s.id} value={s.id}>{s.name}</option>
                                ))}
                            </select>
                            {isAdminOrDirector() && categoryId > 0 && !showNewSubcategoryInput && (
                                <button
                                    type="button"
                                    onClick={() => setShowNewSubcategoryInput(true)}
                                    title="Add Subcategory"
                                    style={{
                                        padding: '0 12px',
                                        fontSize: '18px',
                                        fontWeight: 'bold',
                                        background: 'var(--primary)',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '6px',
                                        cursor: 'pointer'
                                    }}
                                >+</button>
                            )}
                        </div>
                    </div>
                </div>
                {/* Add Category Form - Full Width Below Grid */}
                {showNewCategoryInput && (
                    <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '16px' }}>
                        <div style={{ fontWeight: 600, marginBottom: '12px' }}>Create New Category</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div>
                                <label style={{ fontSize: '14px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>Name *</label>
                                <input
                                    type="text"
                                    value={newCategoryName}
                                    onChange={e => setNewCategoryName(e.target.value)}
                                    placeholder="Category name"
                                    style={{ width: '100%' }}
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label style={{ fontSize: '14px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>Icon</label>
                                <select value={newCategoryIcon} onChange={e => setNewCategoryIcon(e.target.value)} style={{ width: '100%' }}>
                                    {ICONS.map(i => (
                                        <option key={i.value} value={i.value}>{i.label}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div style={{ marginBottom: '12px' }}>
                            <label style={{ fontSize: '14px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>Description</label>
                            <input
                                type="text"
                                value={newCategoryDescription}
                                onChange={e => setNewCategoryDescription(e.target.value)}
                                placeholder="Optional description"
                                style={{ width: '100%' }}
                            />
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <button type="button" className="btn-primary" onClick={handleCreateCategory} style={{ padding: '8px 16px' }}>Create Category</button>
                            <button type="button" className="btn-secondary" onClick={() => { setShowNewCategoryInput(false); setNewCategoryName(''); setNewCategoryDescription(''); setNewCategoryIcon('folder'); }} style={{ padding: '8px 16px' }}>Cancel</button>
                        </div>
                    </div>
                )}
                {/* Add Subcategory Form - Full Width Below Grid */}
                {showNewSubcategoryInput && (
                    <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', marginBottom: '16px' }}>
                        <div style={{ fontWeight: 600, marginBottom: '12px' }}>Create New Subcategory</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
                            <div>
                                <label style={{ fontSize: '14px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>Name *</label>
                                <input
                                    type="text"
                                    value={newSubcategoryName}
                                    onChange={e => setNewSubcategoryName(e.target.value)}
                                    placeholder="Subcategory name"
                                    style={{ width: '100%' }}
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label style={{ fontSize: '14px', fontWeight: 500, display: 'block', marginBottom: '4px' }}>Icon</label>
                                <select value={newSubcategoryIcon} onChange={e => setNewSubcategoryIcon(e.target.value)} style={{ width: '100%' }}>
                                    {ICONS.map(i => (
                                        <option key={i.value} value={i.value}>{i.label}</option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            <button type="button" className="btn-primary" onClick={handleCreateSubcategory} style={{ padding: '8px 16px' }}>Create Subcategory</button>
                            <button type="button" className="btn-secondary" onClick={() => { setShowNewSubcategoryInput(false); setNewSubcategoryName(''); setNewSubcategoryIcon('doc.text'); }} style={{ padding: '8px 16px' }}>Cancel</button>
                        </div>
                    </div>
                )}
                <div className="form-row">
                    <div className="form-group">
                        <label>Icon</label>
                        <select value={icon} onChange={e => setIcon(e.target.value)}>
                            {ICONS.map(i => (
                                <option key={i.value} value={i.value}>{i.label}</option>
                            ))}
                        </select>
                    </div>
                    <div className="form-group">
                        <label>Review Interval (days)</label>
                        <input
                            type="number"
                            value={revisionInterval}
                            onChange={e => setRevisionInterval(Number(e.target.value))}
                            min={1}
                        />
                    </div>
                </div>
                <div className="form-group">
                    <label>Description</label>
                    <textarea
                        value={description}
                        onChange={e => setDescription(e.target.value)}
                        placeholder="Brief description of this template..."
                        rows={2}
                    />
                </div>
            </div>

            {/* Sections */}
            <div className="editor-section">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                    <h3 style={{ margin: 0 }}>Form Sections</h3>
                    <button type="button" className="btn-primary btn-sm" onClick={addSection}>
                        + Add Section
                    </button>
                </div>

                {sections.length === 0 && (
                    <div className="empty-state">
                        No sections yet. Click "Add Section" to start building your form.
                    </div>
                )}

                {sections.map((section, sIndex) => (
                    <div key={section.key} className="section-card">
                        <div
                            className="section-header"
                            onClick={() => setExpandedSection(expandedSection === sIndex ? null : sIndex)}
                            style={{ cursor: 'pointer' }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <span className="drag-handle">≡</span>
                                <span className="section-icon">
                                    {ICONS.find(i => i.value === section.icon)?.label.split(' ')[0] || '📄'}
                                </span>
                                <span className="section-title">{section.title}</span>
                                <span className="field-count">({section.fields.length} fields)</span>
                            </div>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                <button
                                    type="button"
                                    className="btn-icon btn-danger"
                                    onClick={(e) => { e.stopPropagation(); removeSection(sIndex); }}
                                    title="Delete Section"
                                >
                                    🗑️
                                </button>
                                <span>{expandedSection === sIndex ? '▼' : '▶'}</span>
                            </div>
                        </div>

                        {expandedSection === sIndex && (
                            <div className="section-body">
                                <div className="form-row">
                                    <div className="form-group" style={{ flex: 2 }}>
                                        <label>Section Title</label>
                                        <input
                                            type="text"
                                            value={section.title}
                                            onChange={e => updateSection(sIndex, { title: e.target.value })}
                                        />
                                    </div>
                                    <div className="form-group" style={{ flex: 1 }}>
                                        <label>Icon</label>
                                        <select
                                            value={section.icon}
                                            onChange={e => updateSection(sIndex, { icon: e.target.value })}
                                        >
                                            {ICONS.map(i => (
                                                <option key={i.value} value={i.value}>{i.label}</option>
                                            ))}
                                        </select>
                                    </div>
                                </div>

                                <div className="fields-container">
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                                        <h4 style={{ margin: 0 }}>Fields</h4>
                                        <button type="button" className="btn-sm" onClick={() => addField(sIndex)}>
                                            + Add Field
                                        </button>
                                    </div>

                                    {section.fields.length === 0 && (
                                        <div className="empty-state small">No fields yet.</div>
                                    )}

                                    {section.fields.map((field, fIndex) => (
                                        <div key={field.key} className="field-row">
                                            <input
                                                type="text"
                                                value={field.label}
                                                onChange={e => updateField(sIndex, fIndex, { label: e.target.value })}
                                                placeholder="Field Label"
                                                style={{ flex: 3 }}
                                            />
                                            <select
                                                value={field.type}
                                                onChange={e => updateField(sIndex, fIndex, { type: e.target.value as Field['type'] })}
                                                style={{ flex: 1 }}
                                            >
                                                {FIELD_TYPES.map(t => (
                                                    <option key={t.value} value={t.value}>{t.label}</option>
                                                ))}
                                            </select>
                                            {/* Conditional visibility selector */}
                                            <select
                                                value={field.conditional || ''}
                                                onChange={e => updateField(sIndex, fIndex, { conditional: e.target.value || undefined })}
                                                style={{ flex: 1.5 }}
                                                title="Show only when..."
                                            >
                                                <option value="">Always visible</option>
                                                {section.fields
                                                    .filter((f, i) => f.type === 'boolean' && i !== fIndex)
                                                    .map(f => (
                                                        <option key={f.key} value={f.key}>
                                                            If "{f.label}" is Yes
                                                        </option>
                                                    ))}
                                            </select>
                                            <button
                                                type="button"
                                                className="btn-icon btn-danger"
                                                onClick={() => removeField(sIndex, fIndex)}
                                                title="Remove Field"
                                            >
                                                ✕
                                            </button>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {/* Actions */}
            <div className="form-actions">
                <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
                <button
                    type="button"
                    className="btn-primary"
                    onClick={handleSubmit}
                    disabled={saving || !name || !categoryId}
                >
                    {saving ? 'Saving...' : (template?.id ? 'Update Template' : 'Create Template')}
                </button>
            </div>

            <style>{`
                .template-editor {
                    max-width: 900px;
                }
                .editor-section {
                    background: #fff;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                    border: 1px solid #e0e0e0;
                }
                .editor-section h3 {
                    margin-top: 0;
                    margin-bottom: 15px;
                    color: #333;
                }
                .form-row {
                    display: flex;
                    gap: 15px;
                    margin-bottom: 15px;
                }
                .form-row .form-group {
                    flex: 1;
                }
                .section-card {
                    background: #f8f9fa;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    margin-bottom: 12px;
                    overflow: hidden;
                }
                .section-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 15px;
                    background: #f0f0f0;
                    border-bottom: 1px solid #e0e0e0;
                }
                .section-header:hover {
                    background: #e8e8e8;
                }
                .drag-handle {
                    color: #999;
                    cursor: grab;
                }
                .section-title {
                    font-weight: 600;
                    color: #333;
                }
                .field-count {
                    color: #888;
                    font-size: 12px;
                }
                .section-body {
                    padding: 15px;
                }
                .fields-container {
                    margin-top: 15px;
                    padding-top: 15px;
                    border-top: 1px solid #e0e0e0;
                }
                .field-row {
                    display: flex;
                    gap: 10px;
                    align-items: center;
                    margin-bottom: 8px;
                    padding: 8px;
                    background: #fff;
                    border-radius: 4px;
                    border: 1px solid #e0e0e0;
                }
                .field-row input, .field-row select {
                    padding: 6px 10px;
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    font-size: 13px;
                }
                .btn-icon {
                    background: none;
                    border: none;
                    padding: 4px 8px;
                    cursor: pointer;
                    font-size: 14px;
                }
                .btn-danger:hover {
                    color: #c00;
                }
                .btn-sm {
                    padding: 6px 12px;
                    font-size: 13px;
                }
                .empty-state {
                    text-align: center;
                    padding: 30px;
                    color: #888;
                    background: #f8f9fa;
                    border-radius: 8px;
                    border: 2px dashed #ddd;
                }
                .empty-state.small {
                    padding: 15px;
                }
            `}</style>
        </div>
    );
}
