import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { DocumentTemplateEditor } from '../components/DocumentTemplateEditor';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { ClientDocumentForm } from '../components/ClientDocumentForm';

interface Client {
    id: number;
    first_name: string;
    last_name: string;
}



interface TemplateListItem {
    template_id: number;
    template_name: string;
    template_icon: string;
    template_version: number;
    has_document: boolean;
    has_update: boolean;
    is_expired: boolean;
    last_doc_values?: any;
    reference_doc?: any; // Added to hold full doc object including schema
}

const ICON_MAP: Record<string, string> = {
    'doc.text': '📄', 'person': '👤', 'brain.head.profile': '🧠', 'heart': '❤️',
    'bolt.heart': '⚡', 'light.beacon.max': '🚨', 'checkmark.circle': '✅', 'clock': '⏰',
};

function ClientDocumentsTab({ templates, categories }: { templates: any[], categories: any[] }) {
    // ... (state) ...
    const [clients, setClients] = useState<Client[]>([]);
    const [selectedClient, setSelectedClient] = useState<Client | null>(null);
    const [availableTemplates, setAvailableTemplates] = useState<TemplateListItem[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<any>(null);
    const [existingValues, setExistingValues] = useState<Record<string, any>>({});
    const [saving, setSaving] = useState(false);
    const [historyDocs, setHistoryDocs] = useState<any[]>([]);
    const [loadingTemplates, setLoadingTemplates] = useState(false);
    const [isViewingHistory, setIsViewingHistory] = useState(false);

    // New state for side-by-side view
    const [referenceDocument, setReferenceDocument] = useState<any | null>(null);

    // State to store full document info when viewing history
    const [viewingDocument, setViewingDocument] = useState<any | null>(null);



    useEffect(() => {
        api.getClients().then(setClients).catch(console.error);
    }, []);
    useEffect(() => {
        if (selectedClient) {
            setLoadingTemplates(true);
            api.getClientDocuments(selectedClient.id, undefined, true)
                .then((docs: any[]) => {
                    const currentDocs = docs.filter((d: any) => d.is_current);
                    const histDocs = docs.filter((d: any) => !d.is_current);

                    const available = templates.map(t => {
                        const directMatch = currentDocs.find((d: any) => d.template_id === t.id);
                        const olderVersionDoc = currentDocs.find((d: any) =>
                            d.template_name === t.name &&
                            d.template_id !== t.id
                        );
                        const hasUpdate = !directMatch && !!olderVersionDoc;

                        // Calculate if document is expired
                        let isExpired = false;
                        const docToCheck = directMatch || olderVersionDoc;
                        if (docToCheck) {
                            const effectiveDate = new Date(docToCheck.last_reviewed_at || docToCheck.created_at);
                            const intervalDays = docToCheck.revision_interval_days || 365;
                            const expiryDate = new Date(effectiveDate.getTime() + intervalDays * 24 * 60 * 60 * 1000);
                            isExpired = new Date() > expiryDate;
                        }

                        return {
                            template_id: t.id,
                            template_name: t.name,
                            template_icon: t.icon,
                            template_version: t.version,
                            has_document: !!directMatch,
                            has_update: hasUpdate,
                            is_expired: isExpired,
                            last_doc_values: hasUpdate ? olderVersionDoc?.values : undefined,
                            reference_doc: hasUpdate ? olderVersionDoc : undefined
                        };
                    });
                    setAvailableTemplates(available);
                    setHistoryDocs(histDocs);
                })
                .catch(console.error)
                .finally(() => setLoadingTemplates(false));
        } else {
            setAvailableTemplates([]);
            setHistoryDocs([]);
        }
    }, [selectedClient, templates]);

    const handleTemplateSelect = async (item: TemplateListItem) => {
        const template = templates.find(t => t.id === item.template_id);
        if (!template || !selectedClient) return;

        setIsViewingHistory(false);
        setReferenceDocument(null); // Reset by default

        if (item.has_document) {
            // Editing existing
            try {
                const docs = await api.getClientDocuments(selectedClient.id);
                const existingDoc = docs.find((d: any) => d.template_id === item.template_id);
                setExistingValues(existingDoc?.values || {});
                setViewingDocument(existingDoc || null); // Capture document for renewal
            } catch (err) {
                console.error(err);
                setExistingValues({});
            }
        } else if (item.has_update && item.last_doc_values) {
            // New Version - pre-fill AND show reference
            setExistingValues(item.last_doc_values);
            // Enable side-by-side view
            if (item.reference_doc) {
                setReferenceDocument(item.reference_doc);
            }
        } else {
            // New
            setExistingValues({});
        }
        setSelectedTemplate(template);
    };

    const handleHistoryClick = (doc: any) => {
        const template = {
            id: doc.template_id,
            name: doc.template_name,
            description: '', // We'll show this in metadata grid instead
            icon: doc.template_icon,
            form_schema: doc.form_schema,
        };
        setExistingValues(doc.values || {});
        setSelectedTemplate(template);
        setIsViewingHistory(true);
        setReferenceDocument(null);
        setViewingDocument(doc); // Store full document for metadata display
    };

    const handleSave = async (values: Record<string, any>) => {
        if (!selectedClient || !selectedTemplate) return;
        setSaving(true);
        try {
            await api.createClientDocument(selectedClient.id, {
                template_id: selectedTemplate.id,
                values
            });
            alert('Document saved successfully!');
            setSelectedTemplate(null);
            setExistingValues({});
            setReferenceDocument(null);

            // Refresh available templates
            api.getClientDocuments(selectedClient.id, undefined, true)
                .then((docs: any[]) => {
                    const currentDocs = docs.filter((d: any) => d.is_current);
                    const histDocs = docs.filter((d: any) => !d.is_current);

                    const available = templates.map(t => {
                        const directMatch = currentDocs.find((d: any) => d.template_id === t.id);
                        const olderVersionDoc = currentDocs.find((d: any) =>
                            d.template_name === t.name &&
                            d.template_id !== t.id
                        );
                        const hasUpdate = !directMatch && !!olderVersionDoc;

                        // Calculate if document is expired
                        let isExpired = false;
                        const docToCheck = directMatch || olderVersionDoc;
                        if (docToCheck) {
                            const effectiveDate = new Date(docToCheck.last_reviewed_at || docToCheck.created_at);
                            const intervalDays = docToCheck.revision_interval_days || 365;
                            const expiryDate = new Date(effectiveDate.getTime() + intervalDays * 24 * 60 * 60 * 1000);
                            isExpired = new Date() > expiryDate;
                        }

                        return {
                            template_id: t.id,
                            template_name: t.name,
                            template_icon: t.icon,
                            template_version: t.version,
                            has_document: !!directMatch,
                            has_update: hasUpdate,
                            is_expired: isExpired,
                            last_doc_values: hasUpdate ? olderVersionDoc?.values : undefined,
                            reference_doc: hasUpdate ? olderVersionDoc : undefined
                        };
                    });
                    setAvailableTemplates(available);
                    setHistoryDocs(histDocs);
                });
        } catch (err: any) {
            alert(err.message || 'Failed to save document');
        } finally {
            setSaving(false);
        }
    };

    // Review Modal State
    const [reviewModalOpen, setReviewModalOpen] = useState(false);
    const [reviewNotes, setReviewNotes] = useState('');

    const openReviewModal = () => {
        if (!selectedClient || !viewingDocument) return;
        setReviewNotes('Annual review - no changes needed');
        setReviewModalOpen(true);
    };

    const handleConfirmReview = async () => {
        if (!selectedClient || !viewingDocument) return;

        try {
            await api.reviewClientDocument(selectedClient.id, viewingDocument.id, reviewNotes);

            // Close modal first
            setReviewModalOpen(false);

            // Show success feedback? Optional, maybe via toast later. 
            // alerting inside modal actions can be jarring, but keeping pattern for now if consistent
            // or just rely on UI update.
            // alert('Document renewed successfully!'); 

            setSelectedTemplate(null);
            setExistingValues({});
            setViewingDocument(null);
            setIsViewingHistory(false);

            // Refresh available templates
            const docs: any[] = await api.getClientDocuments(selectedClient.id, undefined, true);
            const currentDocs = docs.filter((d: any) => d.is_current);
            const histDocs = docs.filter((d: any) => !d.is_current);

            const available = availableTemplates.map(t => {
                const directMatch = currentDocs.find((d: any) => d.template_id === t.template_id);
                const olderVersionDoc = currentDocs.find((d: any) =>
                    d.template_name === t.template_name &&
                    d.template_id !== t.template_id
                );
                const hasUpdate = !directMatch && !!olderVersionDoc;

                let isExpired = false;
                if (directMatch) {
                    const effectiveDate = new Date(directMatch.last_reviewed_at || directMatch.created_at);
                    const intervalDays = directMatch.revision_interval_days || 365;
                    const expiryDate = new Date(effectiveDate.getTime() + intervalDays * 24 * 60 * 60 * 1000);
                    isExpired = new Date() > expiryDate;
                }

                return {
                    ...t,
                    has_document: !!directMatch,
                    has_update: hasUpdate,
                    is_expired: isExpired,
                    last_doc_values: hasUpdate ? olderVersionDoc?.values : undefined,
                    reference_doc: hasUpdate ? olderVersionDoc : undefined
                };
            });
            setAvailableTemplates(available);
            setHistoryDocs(histDocs);
        } catch (err: any) {
            console.error('Renew error:', err);
            alert(err.message || 'Failed to renew document');
        }
    };

    return (
        <div style={{ padding: '0 20px' }}>
            {selectedTemplate ? (
                referenceDocument ? (
                    // SIDE-BY-SIDE VIEW
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>

                        {/* LEFT: OLD DOCUMENT (ReadOnly) */}
                        <div style={{ borderRight: '1px solid #ddd', paddingRight: '20px' }}>
                            <div style={{ marginBottom: '15px', padding: '10px', background: '#fff3cd', borderRadius: '4px', border: '1px solid #ffeeba' }}>
                                <strong>Reference:</strong> Previous Version (v{referenceDocument.template_version})
                            </div>
                            <ClientDocumentForm
                                template={{
                                    id: referenceDocument.template_id,
                                    name: referenceDocument.template_name,
                                    description: `Archived Version v${referenceDocument.template_version}`,
                                    icon: referenceDocument.template_icon,
                                    form_schema: referenceDocument.form_schema
                                }}
                                existingValues={referenceDocument.values}
                                onSave={() => { }} // No-op
                                onCancel={() => { }} // No cancel on reference side
                                saving={false}
                                readOnly={true}
                                showBackButton={false}
                            />
                        </div>

                        {/* RIGHT: NEW DOCUMENT (Editable) */}
                        <div>
                            <div style={{ marginBottom: '15px', padding: '10px', background: '#d4edda', borderRadius: '4px', border: '1px solid #c3e6cb' }}>
                                <strong>New:</strong> Current Version (v{selectedTemplate.version})
                            </div>
                            <ClientDocumentForm
                                template={selectedTemplate}
                                existingValues={existingValues}
                                onSave={handleSave}
                                onCancel={() => { setSelectedTemplate(null); setExistingValues({}); setIsViewingHistory(false); setReferenceDocument(null); }}
                                saving={saving}
                                readOnly={false}
                                showBackButton={false}
                            />
                        </div>
                    </div>
                ) : (
                    // STANDARD SINGLE VIEW
                    <>

                        {viewingDocument && !isViewingHistory && (
                            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
                                <button
                                    onClick={openReviewModal}
                                    style={{
                                        padding: '8px 16px',
                                        background: '#28a745',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '8px',
                                        fontWeight: 500
                                    }}
                                >
                                    <span>✓</span> Mark as Reviewed without Changes
                                </button>
                            </div>
                        )}
                        <ClientDocumentForm
                            template={selectedTemplate}
                            existingValues={existingValues}
                            onSave={handleSave}
                            onCancel={() => { setSelectedTemplate(null); setExistingValues({}); setIsViewingHistory(false); setReferenceDocument(null); setViewingDocument(null); }}
                            saving={saving}
                            readOnly={isViewingHistory}
                            showBackButton={isViewingHistory}
                            documentDetails={viewingDocument ? {
                                category: categories.find(c => c.id === selectedTemplate.category_id)?.name,
                                subcategory: viewingDocument.subcategory_name || undefined,
                                templateVersion: viewingDocument.template_version,
                                revisionIntervalDays: viewingDocument.revision_interval_days,
                                createdAt: viewingDocument.created_at,
                                createdByName: viewingDocument.created_by_name,
                                lastReviewedAt: viewingDocument.last_reviewed_at,
                                lastReviewedBy: viewingDocument.last_reviewed_by_name,
                                changesMade: viewingDocument.last_review_changes_made
                            } : undefined}
                        />
                    </>
                )
            ) : (
                <>
                    <div style={{ marginBottom: '20px' }}>
                        <label style={{ fontWeight: 600, marginBottom: '8px', display: 'block' }}>Select Client</label>
                        <select
                            style={{ padding: '10px', fontSize: '14px', minWidth: '300px', borderRadius: '6px', border: '1px solid #ddd' }}
                            value={selectedClient?.id || ''}
                            onChange={e => {
                                const client = clients.find(c => c.id === Number(e.target.value));
                                setSelectedClient(client || null);
                            }}
                        >
                            <option value="">-- Select a client --</option>
                            {clients.map(c => (
                                <option key={c.id} value={c.id}>{c.first_name} {c.last_name}</option>
                            ))}
                        </select>
                    </div>

                    {selectedClient && (
                        <>
                            <h3 style={{ marginBottom: '15px' }}>
                                Documents for {selectedClient.first_name} {selectedClient.last_name}
                            </h3>
                            {loadingTemplates ? (
                                <p>Loading templates...</p>
                            ) : (
                                <>
                                    {availableTemplates.length === 0 ? (
                                        <p style={{ color: '#888', marginBottom: '30px' }}>No document templates available.</p>
                                    ) : (
                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '12px', marginBottom: '30px' }}>
                                            {availableTemplates.map(item => (
                                                <div
                                                    key={item.template_id}
                                                    onClick={() => handleTemplateSelect(item)}
                                                    style={{
                                                        background: '#fff',
                                                        border: item.is_expired ? '2px solid #dc3545' : item.has_document ? '2px solid #28a745' : item.has_update ? '2px solid #ffc107' : '1px solid #ddd',
                                                        borderRadius: '8px',
                                                        padding: '15px',
                                                        cursor: 'pointer',
                                                        transition: 'box-shadow 0.2s',
                                                        position: 'relative'
                                                    }}
                                                    onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'}
                                                    onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
                                                >
                                                    {item.is_expired && (
                                                        <div style={{
                                                            position: 'absolute',
                                                            top: '-10px',
                                                            right: '-10px',
                                                            background: '#dc3545',
                                                            color: '#fff',
                                                            fontSize: '10px',
                                                            fontWeight: 'bold',
                                                            padding: '4px 8px',
                                                            borderRadius: '12px',
                                                            boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
                                                            zIndex: 2
                                                        }}>
                                                            EXPIRED
                                                        </div>
                                                    )}
                                                    {item.has_update && (
                                                        <div style={{
                                                            position: 'absolute',
                                                            top: '-10px',
                                                            right: item.is_expired ? '60px' : '-10px',
                                                            background: '#ffc107',
                                                            color: '#000',
                                                            fontSize: '10px',
                                                            fontWeight: 'bold',
                                                            padding: '4px 8px',
                                                            borderRadius: '12px',
                                                            boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
                                                            zIndex: 1
                                                        }}>
                                                            UPDATE AVAILABLE
                                                        </div>
                                                    )}
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                        <span style={{ fontSize: '24px' }}>{ICON_MAP[item.template_icon] || '📄'}</span>
                                                        <div>
                                                            <div style={{ fontWeight: 600, fontSize: '14px' }}>{item.template_name}</div>
                                                            {/* Status Message: Expiration or Document Status */}
                                                            {item.is_expired ? (
                                                                <div style={{ fontSize: '11px', color: '#dc3545' }}>⚠ Document Expired</div>
                                                            ) : item.has_document && !item.has_update ? (
                                                                <div style={{ fontSize: '11px', color: '#28a745' }}>✓ Has document</div>
                                                            ) : null}

                                                            {/* Status Message: Update Available */}
                                                            {item.has_update && (
                                                                <div style={{ fontSize: '11px', color: '#e6a700', marginTop: item.is_expired ? '2px' : '0' }}>
                                                                    ⚠ New template version available
                                                                </div>
                                                            )}

                                                            {/* Fallback */}
                                                            {!item.is_expired && !item.has_document && !item.has_update && (
                                                                <div style={{ fontSize: '11px', color: '#888' }}>No document yet</div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}


                                    {historyDocs.length > 0 && (
                                        <div style={{ marginTop: '40px' }}>
                                            <h4 style={{ marginBottom: '15px', color: '#666' }}>Document History</h4>
                                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                                                <thead>
                                                    <tr style={{ background: '#f8f9fa', color: '#666', textAlign: 'left' }}>
                                                        <th style={{ padding: '10px', borderBottom: '1px solid #ddd' }}>Document</th>
                                                        <th style={{ padding: '10px', borderBottom: '1px solid #ddd' }}>Template Version</th>
                                                        <th style={{ padding: '10px', borderBottom: '1px solid #ddd' }}>Creation Date</th>
                                                        <th style={{ padding: '10px', borderBottom: '1px solid #ddd' }}>Created By</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {historyDocs.map((doc: any) => (
                                                        <tr
                                                            key={doc.id}
                                                            style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}
                                                            onClick={() => handleHistoryClick(doc)}
                                                            onMouseEnter={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                                                            onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                                                        >
                                                            <td style={{ padding: '10px' }}>
                                                                <span style={{ marginRight: '8px' }}>{ICON_MAP[doc.template_icon] || '📄'}</span>
                                                                {doc.template_name}
                                                            </td>
                                                            <td style={{ padding: '10px' }}>
                                                                v{doc.template_version || '?'}
                                                            </td>
                                                            <td style={{ padding: '10px' }}>
                                                                {new Date(doc.created_at).toLocaleString()}
                                                            </td>
                                                            <td style={{ padding: '10px' }}>
                                                                {doc.created_by_name || 'Unknown'}
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </>
                            )}
                        </>
                    )}
                </>
            )
            }
            {reviewModalOpen && (
                <div className="modal-overlay" onClick={() => setReviewModalOpen(false)}>
                    <div className="modal" onClick={e => e.stopPropagation()}>
                        <h2>Mark as Reviewed</h2>
                        <div className="form-group">
                            <label>Review Notes</label>
                            <textarea
                                value={reviewNotes}
                                onChange={e => setReviewNotes(e.target.value)}
                                rows={4}
                                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ddd' }}
                            />
                        </div>
                        <div className="form-actions">
                            <button className="btn-secondary" onClick={() => setReviewModalOpen(false)}>Cancel</button>
                            <button className="btn-primary" onClick={handleConfirmReview}>Confirm Review</button>
                        </div>
                    </div>
                </div>
            )}
        </div >
    );
}
interface DocumentTemplate {
    id: number;
    name: string;
    description: string | null;
    category_id: number;
    subcategory_id: number | null;
    icon: string;
    version: number;
    revision_interval_days: number;
    form_schema: { sections: any[] };
    is_archived: boolean;
    created_by_name: string | null;
    created_at: string | null;
}

interface DocumentCategory {
    id: number;
    name: string;
    description: string | null;
    icon: string | null;
    is_active: boolean;
}
export function Documents() {
    const { user } = useAuth();
    const canManageTemplates = user?.role_id === 1 || user?.role_id === 2;

    const [templates, setTemplates] = useState<DocumentTemplate[]>([]);
    const [archivedTemplates, setArchivedTemplates] = useState<DocumentTemplate[]>([]);
    const [categories, setCategories] = useState<DocumentCategory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    // Editor state
    const [showEditor, setShowEditor] = useState(false);
    const [editingTemplate, setEditingTemplate] = useState<DocumentTemplate | null>(null);
    const [saving, setSaving] = useState(false);

    // Active tab
    // Default to 'documents' if user cannot manage templates
    const [activeTab, setActiveTab] = useState<'templates' | 'documents'>(
        canManageTemplates ? 'templates' : 'documents'
    );

    useEffect(() => {
        // Enforce access control if somehow activeTab is templates (e.g. explicitly set)
        if (!canManageTemplates && activeTab === 'templates') {
            setActiveTab('documents');
        }
    }, [canManageTemplates, activeTab]);

    // Viewing archived template in read-only mode
    const [viewingArchivedTemplate, setViewingArchivedTemplate] = useState<DocumentTemplate | null>(null);

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

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        setLoading(true);
        try {
            const [activeTemplates, archivedTemplatesData, categoriesData] = await Promise.all([
                api.getDocumentTemplates(false),  // is_archived=false = active templates
                api.getDocumentTemplates(true),   // is_archived=true = archived templates
                api.getDocumentCategories(),
            ]);
            setTemplates(activeTemplates);
            setArchivedTemplates(archivedTemplatesData);
            setCategories(categoriesData);
        } catch (err) {
            console.error(err);
            setError('Failed to load data');
        } finally {
            setLoading(false);
        }
    };

    const reloadCategories = async () => {
        try {
            const categoriesData = await api.getDocumentCategories();
            setCategories(categoriesData);
        } catch (err) {
            console.error('Failed to reload categories', err);
        }
    };

    const handleCreate = () => {
        setEditingTemplate(null);
        setShowEditor(true);
    };

    const handleEdit = (template: DocumentTemplate) => {
        setEditingTemplate(template);
        setShowEditor(true);
    };

    const handleArchive = (template: DocumentTemplate) => {
        setConfirmation({
            isOpen: true,
            title: 'Archive Template',
            message: `Are you sure you want to archive "${template.name}"?\n\nThis will inactivate all documents created with this template.`,
            variant: 'danger',
            action: async () => {
                try {
                    await api.deleteDocumentTemplate(template.id);
                    setConfirmation(prev => ({ ...prev, isOpen: false }));
                    loadData();
                } catch (err) {
                    alert('Failed to archive template');
                }
            }
        });
    };

    const handleSave = async (data: any) => {
        // ... (same as before) ...
        setSaving(true);
        try {
            if (editingTemplate) {
                await api.updateDocumentTemplate(editingTemplate.id, data);
            } else {
                await api.createDocumentTemplate(data);
            }
            setShowEditor(false);
            setEditingTemplate(null);
            loadData();
        } catch (err: any) {
            alert(err.message || 'Failed to save template');
        } finally {
            setSaving(false);
        }
    };

    const getCategoryName = (id: number) => categories.find(c => c.id === id)?.name || 'Unknown';

    return (
        <div className="page">
            <div className="page-header">
                <h2>Documents</h2>
            </div>

            {/* Tabs */}
            <div className="tabs" style={{ marginBottom: '20px', borderBottom: '1px solid #ddd' }}>
                {/* ... (tabs rendering same as before) ... */}
                {(['templates', 'documents'] as const).map(tab => {
                    // Hide templates tab if not authorized
                    if (tab === 'templates' && !canManageTemplates) return null;

                    return (
                        <button
                            key={tab}
                            style={{
                                padding: '10px 20px',
                                marginRight: '5px',
                                border: 'none',
                                background: 'none',
                                borderBottom: activeTab === tab ? '2px solid #0056b3' : 'none',
                                color: activeTab === tab ? '#0056b3' : '#666',
                                fontWeight: activeTab === tab ? 'bold' : 'normal',
                                cursor: 'pointer',
                                textTransform: 'capitalize'
                            }}
                            onClick={() => setActiveTab(tab)}
                        >
                            {tab === 'templates' && '📄 Templates'}
                            {tab === 'documents' && '📋 Client Documents'}
                        </button>
                    );
                })}
            </div>

            {activeTab === 'templates' && (
                <>
                    {viewingArchivedTemplate ? (
                        // Read-only view of archived template
                        <div style={{ padding: '0 20px' }}>
                            <div style={{ marginBottom: '20px' }}>
                                <button
                                    className="btn-secondary"
                                    onClick={() => setViewingArchivedTemplate(null)}
                                    style={{ marginBottom: '15px' }}
                                >
                                    ← Back to Templates
                                </button>
                                <div style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '12px',
                                    padding: '15px',
                                    background: '#f8f9fa',
                                    borderRadius: '8px',
                                    border: '1px solid #dee2e6'
                                }}>
                                    <span style={{ fontSize: '28px', filter: 'grayscale(50%)' }}>
                                        {ICON_MAP[viewingArchivedTemplate.icon] || '📄'}
                                    </span>
                                    <div>
                                        <h3 style={{ margin: 0, color: '#495057' }}>
                                            {viewingArchivedTemplate.name}
                                            <span style={{
                                                marginLeft: '10px',
                                                fontSize: '12px',
                                                padding: '3px 8px',
                                                background: '#6c757d',
                                                color: '#fff',
                                                borderRadius: '4px'
                                            }}>ARCHIVED</span>
                                        </h3>
                                        <p style={{ margin: '5px 0 0 0', color: '#6c757d', fontSize: '13px' }}>
                                            Version {viewingArchivedTemplate.version}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Template Metadata */}
                            <div style={{
                                background: '#fff',
                                border: '1px solid #dee2e6',
                                borderRadius: '8px',
                                padding: '20px',
                                marginBottom: '20px'
                            }}>
                                <h4 style={{ marginTop: 0, marginBottom: '15px', color: '#495057', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>
                                    Template Details
                                </h4>

                                {viewingArchivedTemplate.description && (
                                    <p style={{ color: '#666', marginBottom: '20px', fontStyle: 'italic', background: '#f8f9fa', padding: '10px', borderRadius: '4px' }}>
                                        {viewingArchivedTemplate.description}
                                    </p>
                                )}

                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '15px' }}>
                                    <div>
                                        <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Category</div>
                                        <div style={{ fontWeight: 500, color: '#333' }}>{getCategoryName(viewingArchivedTemplate.category_id)}</div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Subcategory</div>
                                        <div style={{ fontWeight: 500, color: '#333' }}>
                                            {viewingArchivedTemplate.subcategory_id
                                                ? categories.find(c => c.id === viewingArchivedTemplate.subcategory_id)?.name || 'Unknown'
                                                : '—'}
                                        </div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Revision Interval</div>
                                        <div style={{ fontWeight: 500, color: '#333' }}>
                                            {viewingArchivedTemplate.revision_interval_days} days
                                        </div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Created</div>
                                        <div style={{ fontWeight: 500, color: '#333' }}>
                                            {viewingArchivedTemplate.created_at
                                                ? new Date(viewingArchivedTemplate.created_at).toLocaleDateString()
                                                : '—'}
                                        </div>
                                    </div>
                                    <div>
                                        <div style={{ fontSize: '11px', color: '#888', textTransform: 'uppercase', marginBottom: '4px' }}>Created By</div>
                                        <div style={{ fontWeight: 500, color: '#333' }}>
                                            {viewingArchivedTemplate.created_by_name || '—'}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Form Sections */}
                            <div style={{ background: '#fff', border: '1px solid #dee2e6', borderRadius: '8px', padding: '20px' }}>
                                <h4 style={{ marginTop: 0, marginBottom: '15px', color: '#495057', borderBottom: '1px solid #eee', paddingBottom: '10px' }}>
                                    Form Sections ({viewingArchivedTemplate.form_schema?.sections?.length || 0})
                                </h4>
                                {viewingArchivedTemplate.form_schema?.sections?.length ? (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                                        {viewingArchivedTemplate.form_schema.sections.map((section: any, idx: number) => (
                                            <div key={idx} style={{
                                                border: '1px solid #e9ecef',
                                                borderRadius: '6px',
                                                padding: '15px',
                                                background: '#fafafa'
                                            }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                                                    <span style={{
                                                        width: '24px',
                                                        height: '24px',
                                                        borderRadius: '50%',
                                                        background: '#6c757d',
                                                        color: '#fff',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        fontSize: '12px',
                                                        fontWeight: 'bold'
                                                    }}>{idx + 1}</span>
                                                    {section.icon && <span style={{ fontSize: '18px' }}>{ICON_MAP[section.icon] || '📋'}</span>}
                                                    <span style={{ fontWeight: 600, color: '#495057' }}>{section.title}</span>
                                                    <span style={{ fontSize: '11px', color: '#888', marginLeft: 'auto' }}>
                                                        {section.fields?.length || 0} fields
                                                    </span>
                                                </div>

                                                {section.fields?.length > 0 && (
                                                    <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
                                                        <thead>
                                                            <tr style={{ background: '#e9ecef' }}>
                                                                <th style={{ padding: '6px 10px', textAlign: 'left', width: '40px' }}>#</th>
                                                                <th style={{ padding: '6px 10px', textAlign: 'left' }}>Field Key</th>
                                                                <th style={{ padding: '6px 10px', textAlign: 'left' }}>Label</th>
                                                                <th style={{ padding: '6px 10px', textAlign: 'left' }}>Type</th>
                                                                <th style={{ padding: '6px 10px', textAlign: 'left' }}>Visibility</th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {section.fields.map((field: any, fIdx: number) => {
                                                                const conditionalRef = field.conditional ? section.fields.find((f: any) => f.key === field.conditional) : null;
                                                                return (
                                                                    <tr key={fIdx} style={{ borderBottom: '1px solid #eee' }}>
                                                                        <td style={{ padding: '6px 10px', color: '#888' }}>{fIdx + 1}</td>
                                                                        <td style={{ padding: '6px 10px', fontFamily: 'monospace', fontSize: '12px', color: '#666' }}>{field.key}</td>
                                                                        <td style={{ padding: '6px 10px' }}>{field.label}</td>
                                                                        <td style={{ padding: '6px 10px' }}>
                                                                            <span style={{
                                                                                padding: '2px 6px',
                                                                                borderRadius: '3px',
                                                                                fontSize: '11px'
                                                                            }}>{field.type}</span>
                                                                        </td>
                                                                        <td style={{ padding: '6px 10px', fontSize: '12px', color: '#555' }}>
                                                                            {conditionalRef ? (
                                                                                <span style={{ background: '#fff3cd', padding: '2px 6px', borderRadius: '4px', border: '1px solid #ffeeba' }}>
                                                                                    If <strong>{conditionalRef.label}</strong> is Yes
                                                                                </span>
                                                                            ) : (
                                                                                <span style={{ color: '#aaa' }}>Always</span>
                                                                            )}
                                                                        </td>
                                                                    </tr>
                                                                );
                                                            })}
                                                        </tbody>
                                                    </table>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p style={{ color: '#888' }}>No sections defined in this template.</p>
                                )}
                            </div>
                        </div>
                    ) : showEditor ? (
                        <div style={{ padding: '0 20px' }}>
                            <h3 style={{ marginBottom: '20px' }}>
                                {editingTemplate ? `Edit: ${editingTemplate.name}` : 'Create New Template'}
                            </h3>
                            <DocumentTemplateEditor
                                template={editingTemplate ? {
                                    id: editingTemplate.id,
                                    name: editingTemplate.name,
                                    description: editingTemplate.description || '',
                                    category_id: editingTemplate.category_id,
                                    subcategory_id: editingTemplate.subcategory_id,
                                    icon: editingTemplate.icon,
                                    revision_interval_days: editingTemplate.revision_interval_days,
                                    form_schema: editingTemplate.form_schema
                                } : undefined}
                                categories={categories.map(c => ({ id: c.id, name: c.name }))}
                                onSave={handleSave}
                                onCancel={() => { setShowEditor(false); setEditingTemplate(null); }}
                                onCategoriesChanged={reloadCategories}
                                saving={saving}
                            />
                        </div>
                    ) : (
                        <div style={{ padding: '0 20px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                                <h3 style={{ margin: 0 }}>Document Templates</h3>
                                <button className="btn-primary" onClick={handleCreate}>
                                    + New Template
                                </button>
                            </div>

                            {loading ? (
                                <p>Loading templates...</p>
                            ) : error ? (
                                <p style={{ color: 'red' }}>{error}</p>
                            ) : (
                                <>
                                    {templates.length === 0 ? (
                                        <div style={{
                                            textAlign: 'center',
                                            padding: '40px',
                                            background: '#f8f9fa',
                                            borderRadius: '8px',
                                            border: '2px dashed #ddd'
                                        }}>
                                            <p style={{ color: '#666', marginBottom: '15px' }}>
                                                No templates yet. Create your first document template.
                                            </p>
                                            <button className="btn-primary" onClick={handleCreate}>
                                                + Create Template
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="template-grid" style={{
                                            display: 'grid',
                                            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                                            gap: '16px'
                                        }}>
                                            {templates.map(template => (
                                                <div key={template.id} className="template-card" style={{
                                                    background: '#fff',
                                                    border: '1px solid #e0e0e0',
                                                    borderRadius: '10px',
                                                    padding: '20px',
                                                    transition: 'box-shadow 0.2s',
                                                    cursor: 'pointer'
                                                }}
                                                    onClick={() => handleEdit(template)}
                                                    onMouseEnter={e => e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)'}
                                                    onMouseLeave={e => e.currentTarget.style.boxShadow = 'none'}
                                                >
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
                                                        <span style={{ fontSize: '28px' }}>
                                                            {ICON_MAP[template.icon] || '📄'}
                                                        </span>
                                                        <div>
                                                            <h4 style={{ margin: 0, fontSize: '16px', color: '#333' }}>
                                                                {template.name}
                                                            </h4>
                                                            <span style={{ fontSize: '12px', color: '#888' }}>
                                                                {getCategoryName(template.category_id)}
                                                            </span>
                                                        </div>
                                                    </div>
                                                    {template.description && (
                                                        <p style={{
                                                            fontSize: '13px',
                                                            color: '#666',
                                                            margin: '0 0 12px 0',
                                                            lineHeight: '1.4'
                                                        }}>
                                                            {template.description}
                                                        </p>
                                                    )}
                                                    <div style={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center',
                                                        borderTop: '1px solid #f0f0f0',
                                                        paddingTop: '12px',
                                                        marginTop: '8px'
                                                    }}>
                                                        <span style={{ fontSize: '11px', color: '#999' }}>
                                                            v{template.version} • {template.form_schema?.sections?.length || 0} sections
                                                        </span>
                                                        <div style={{ display: 'flex', gap: '8px' }} onClick={e => e.stopPropagation()}>
                                                            <button
                                                                className="btn-sm"
                                                                onClick={() => handleEdit(template)}
                                                                style={{ padding: '4px 10px', fontSize: '12px' }}
                                                            >
                                                                Create New Version
                                                            </button>
                                                            <button
                                                                className="btn-sm btn-danger"
                                                                onClick={() => handleArchive(template)}
                                                                style={{
                                                                    padding: '4px 10px',
                                                                    fontSize: '12px',
                                                                    background: '#fff',
                                                                    border: '1px solid #dc3545',
                                                                    color: '#dc3545'
                                                                }}
                                                            >
                                                                Archive Template
                                                            </button>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {/* Archived Templates Section - Table View */}
                                    {archivedTemplates.length > 0 && (
                                        <div style={{ marginTop: '40px', borderTop: '1px solid #eee', paddingTop: '20px' }}>
                                            <h4 style={{ color: '#666', marginBottom: '15px' }}>📂 Archived Templates</h4>
                                            <table style={{ width: '100%', borderCollapse: 'collapse', background: '#fff', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                                                <thead>
                                                    <tr style={{ background: '#f8f9fa', color: '#666', textAlign: 'left' }}>
                                                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Template</th>
                                                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Category</th>
                                                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Version</th>
                                                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Sections</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {archivedTemplates.map(template => (
                                                        <tr
                                                            key={template.id}
                                                            onClick={() => setViewingArchivedTemplate(template)}
                                                            style={{ cursor: 'pointer', transition: 'background 0.15s' }}
                                                            onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'}
                                                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                                        >
                                                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #eee' }}>
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                                                    <span style={{ fontSize: '18px', filter: 'grayscale(50%)' }}>
                                                                        {ICON_MAP[template.icon] || '📄'}
                                                                    </span>
                                                                    <span style={{ fontWeight: 500, color: '#555' }}>{template.name}</span>
                                                                </div>
                                                            </td>
                                                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #eee', color: '#666' }}>
                                                                {getCategoryName(template.category_id)}
                                                            </td>
                                                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #eee', color: '#888' }}>
                                                                v{template.version}
                                                            </td>
                                                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #eee', color: '#888' }}>
                                                                {template.form_schema?.sections?.length || 0} sections
                                                            </td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </>
            )}

            {/* Client Documents Tab */}
            {activeTab === 'documents' && (
                <ClientDocumentsTab
                    templates={templates}
                    categories={categories}
                />
            )}

            {viewingArchivedTemplate && (
                // ... (viewing archived template logic is handled above in the main render flow, 
                // but this closing tag suggests we are at the end of the return)
                // Actually, let's just place the modal at the end of the outermost div
                <></>
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
