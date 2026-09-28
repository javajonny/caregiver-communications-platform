export const API_BASE = 'https://localhost:8443';

async function fetchWithAuth(url: string, options: RequestInit = {}) {
    // FIX: Must use sessionStorage now!
    const token = sessionStorage.getItem('token');

    const res = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...options.headers,
        },
    });

    if (res.status === 401 || res.status === 403) {
        sessionStorage.removeItem('token');
        // Dispatch event so AuthContext can logout
        window.dispatchEvent(new Event('auth:unauthorized'));
        throw new Error('Unauthorized');
    }

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Request failed' }));

        let errorMessage = error.detail || 'Request failed';

        // Handle Pydantic validation errors (array)
        if (Array.isArray(errorMessage)) {
            errorMessage = errorMessage.map((e: any) => {
                if (e.msg) {
                    // Clean up Pydantic messages
                    const msg = e.msg.replace(/^Value error, /, '');
                    // format: "work_email: invalid email address"
                    const field = e.loc ? e.loc[e.loc.length - 1] : 'Error';
                    return `${field}: ${msg}`;
                }
                return JSON.stringify(e);
            }).join('\n');
        } else if (typeof errorMessage === 'object') {
            errorMessage = JSON.stringify(errorMessage);
        }

        const errorObj: any = new Error(errorMessage);
        errorObj.status = res.status;
        throw errorObj;
    }

    return res;
}

export const api = {
    // Clients
    getClients: () => fetchWithAuth('/clients').then(r => r.json()),
    getClient: (id: number) => fetchWithAuth(`/clients/${id}`).then(r => r.json()),
    createClient: (data: object) => fetchWithAuth('/clients', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateClient: (id: number, data: object) => fetchWithAuth(`/clients/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteClient: (id: number) => fetchWithAuth(`/clients/${id}`, {
        method: 'DELETE',
    }),

    // Client Contacts
    getClientContacts: (clientId: number) => fetchWithAuth(`/clients/${clientId}/contacts`).then(r => r.json()),
    createClientContact: (data: object) => fetchWithAuth('/clients/contacts', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateClientContact: (contactId: number, data: object) => fetchWithAuth(`/clients/contacts/${contactId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteClientContact: (contactId: number) => fetchWithAuth(`/clients/contacts/${contactId}`, {
        method: 'DELETE',
    }),

    // Client Program Enrollments
    getClientEnrollments: (clientId: number) => fetchWithAuth(`/clients/${clientId}/enrollments`).then(r => r.json()),

    uploadClientProfileImage: (clientId: number, file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const token = localStorage.getItem('token');
        return fetch(`${API_BASE}/clients/${clientId}/profile-image`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            body: formData,
        }).then(r => {
            if (!r.ok) throw new Error('Upload failed');
            return r.json();
        });
    },

    // Client Behaviors
    getClientBehaviors: (clientId: number) => fetchWithAuth(`/clients/${clientId}/behaviors`).then(r => r.json()),

    // Behavior Configuration Management
    getBehaviorTypes: () => fetchWithAuth(`/clients/behavior-types`).then(r => r.json()),
    createBehaviorType: (data: { name: string; description?: string }) =>
        fetchWithAuth(`/behavior-types`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).then(r => r.json()),
    getClientBehaviorConfigs: (clientId: number) => fetchWithAuth(`/clients/${clientId}/behavior-configs`).then(r => r.json()),
    createClientBehaviorConfig: (clientId: number, data: { behavior_type_ids: number[]; notes?: string }) =>
        fetchWithAuth(`/clients/${clientId}/behavior-configs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        }).then(r => r.json()),
    deleteClientBehaviorConfig: (clientId: number, configId: number) =>
        fetchWithAuth(`/clients/${clientId}/behavior-configs/${configId}`, { method: 'DELETE' }),

    // Client Updates
    getClientUpdates: (clientId: number) => fetchWithAuth(`/clients/${clientId}/updates`).then(r => r.json()),

    // Client Documents
    getClientDocuments: (clientId: number, categoryId?: number, include_history = false) =>
        fetchWithAuth(`/clients/${clientId}/documents?${categoryId ? `category_id=${categoryId}&` : ''}${include_history ? 'include_history=true' : ''}`).then(r => r.json()),

    createClientDocument: (clientId: number, data: { template_id: number; values: object; revision_notes?: string }) =>
        fetchWithAuth(`/clients/${clientId}/documents`, {
            method: 'POST',
            body: JSON.stringify(data),
        }).then(r => r.json()),

    reviewClientDocument: (clientId: number, documentId: number, notes?: string) =>
        fetchWithAuth(`/clients/${clientId}/documents/${documentId}/review?notes=${encodeURIComponent(notes || '')}`, {
            method: 'POST',
        }).then(r => r.json()),

    createClientEnrollment: (data: object) => fetchWithAuth('/clients/enrollments', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateClientEnrollment: (enrollmentId: number, data: object) => fetchWithAuth(`/clients/enrollments/${enrollmentId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteClientEnrollment: (enrollmentId: number) => fetchWithAuth(`/clients/enrollments/${enrollmentId}`, {
        method: 'DELETE',
    }),

    // Staff
    getStaff: () => fetchWithAuth('/staff').then(r => r.json()),
    getStaffMember: (id: number) => fetchWithAuth(`/staff/${id}`).then(r => r.json()),
    createStaff: (data: object) => fetchWithAuth('/staff', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateStaff: (id: number, data: object) => fetchWithAuth(`/staff/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteStaff: (id: number) => fetchWithAuth(`/staff/${id}`, {
        method: 'DELETE',
    }).then(r => r.json()),
    resetPassword: (id: number, password: string) => fetchWithAuth(`/staff/${id}/reset-password`, {
        method: 'POST',
        body: JSON.stringify({ password }),
    }),
    uploadStaffProfileImage: (staffId: number, file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        const token = localStorage.getItem('token');
        return fetch(`${API_BASE}/staff/${staffId}/profile-image`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
            },
            body: formData,
        }).then(r => {
            if (!r.ok) throw new Error('Upload failed');
            return r.json();
        });
    },

    // Shifts
    getShifts: () => fetchWithAuth('/shifts').then(r => r.json()),
    getShift: (id: number) => fetchWithAuth(`/shifts/${id}`).then(r => r.json()),
    createShift: (data: object) => fetchWithAuth('/shifts', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    createShiftFromTemplate: (data: { shift_template_id: number, start_date: string, repeat_weeks?: number, assignments?: Record<number, number> }) => fetchWithAuth('/shifts/from-template', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateShift: (id: number, data: object) => fetchWithAuth(`/shifts/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteShift: (id: number) => fetchWithAuth(`/shifts/${id}`, {
        method: 'DELETE',
    }),

    // Shift Templates
    getShiftTemplates: () => fetchWithAuth('/shifts/templates').then(r => r.json()),
    getShiftTemplate: (id: number) => fetchWithAuth(`/shifts/templates/${id}`).then(r => r.json()),
    createShiftTemplate: (data: object) => fetchWithAuth('/shifts/templates', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateShiftTemplate: (id: number, data: object) => fetchWithAuth(`/shifts/templates/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteShiftTemplate: (id: number) => fetchWithAuth(`/shifts/templates/${id}`, {
        method: 'DELETE',
    }),

    // Shift Positions
    createShiftPosition: (data: object) => fetchWithAuth('/shifts/positions', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateShiftPosition: (id: number, data: object) => fetchWithAuth(`/shifts/positions/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteShiftPosition: (id: number) => fetchWithAuth(`/shifts/positions/${id}`, {
        method: 'DELETE',
    }),

    // Shift Position Tasks
    createShiftPositionTask: (data: object) => fetchWithAuth('/shifts/position-tasks', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateShiftPositionTask: (id: number, data: object) => fetchWithAuth(`/shifts/position-tasks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteShiftPositionTask: (id: number) => fetchWithAuth(`/shifts/position-tasks/${id}`, {
        method: 'DELETE',
    }),

    // Tasks (Library)
    getTasks: () => fetchWithAuth('/shifts/tasks').then(r => r.json()),
    createTask: (data: object) => fetchWithAuth('/shifts/tasks', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateTask: (id: number, data: object) => fetchWithAuth(`/shifts/tasks/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteTask: (id: number) => fetchWithAuth(`/shifts/tasks/${id}`, {
        method: 'DELETE',
    }),

    // Task Categories
    getTaskCategories: () => fetchWithAuth('/shifts/task-categories').then(r => r.json()),

    // Shift Assignments
    getShiftAssignments: (shiftId: number) => fetchWithAuth(`/shifts/${shiftId}/assignments`).then(r => r.json()),
    getAvailableStaffForShift: (shiftId: number) => fetchWithAuth(`/shifts/${shiftId}/available-staff`).then(r => r.json()),
    getAvailableStaffForTemplate: (templateId: number, startDate: string) =>
        fetchWithAuth(`/shifts/templates/${templateId}/available-staff?start_date=${startDate}`).then(r => r.json()),
    createShiftAssignment: (shiftId: number, data: object) => fetchWithAuth(`/shifts/${shiftId}/assignments`, {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    deleteShiftAssignment: (assignmentId: number) => fetchWithAuth(`/shifts/assignments/${assignmentId}`, {
        method: 'DELETE',
    }),
    getShiftTaskStatuses: (shiftId: number) => fetchWithAuth(`/shifts/${shiftId}/task-status`).then(r => r.json()),
    getShiftLogs: (shiftId: number) => fetchWithAuth(`/shifts/${shiftId}/logs`).then(r => r.json()),

    // Locations
    getLocations: () => fetchWithAuth('/locations/programs').then(r => r.json()),
    createProgramLocation: (data: object) => fetchWithAuth('/locations/programs', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),

    // Addresses
    getAddresses: () => fetchWithAuth('/locations/addresses').then(r => r.json()),
    createAddress: (data: object) => fetchWithAuth('/locations/addresses', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),

    // Residence Types
    getResidenceTypes: () => fetchWithAuth('/locations/residence-types').then(r => r.json()),

    // Client Residence
    createClientResidence: (data: object) => fetchWithAuth('/clients/residence', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),

    getClientResidence: (clientId: number) => fetchWithAuth(`/clients/${clientId}/residence`).then(r => r.json()),
    getClientResidenceHistory: (clientId: number) => fetchWithAuth(`/clients/${clientId}/residence/history`).then(r => r.json()),
    updateClientResidence: (clientId: number, residenceId: number, data: object) => fetchWithAuth(`/clients/${clientId}/residence/${residenceId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    endClientResidence: (clientId: number) => fetchWithAuth(`/clients/${clientId}/residence`, {
        method: 'DELETE',
    }).then(r => r.json()),

    // Relationship Types (for contacts)
    getRelationshipTypes: () => fetchWithAuth('/locations/relationship-types').then(r => r.json()),

    // Location Types
    getLocationTypes: () => fetchWithAuth('/locations/types').then(r => r.json()),

    // Dashboard stats for past shifts
    getShiftDashboardStats: () => fetchWithAuth('/shifts/dashboard-stats').then(r => r.json()),

    // Stats for dashboard
    getStats: async () => {
        const [clients, staff, expiredRes] = await Promise.all([
            fetchWithAuth('/clients').then(r => r.json()),
            fetchWithAuth('/staff').then(r => r.json()),
            fetchWithAuth('/documents/expired/count').then(r => r.json()),
        ]);
        return {
            totalClients: clients.length,
            totalStaff: staff.length,
            expiredDocuments: expiredRes.count,
        };
    },

    getExpiredDocuments: () => fetchWithAuth('/documents/expired').then(r => r.json()),

    // Document Templates
    getDocumentTemplates: (isArchived?: boolean) =>
        fetchWithAuth(`/documents/templates${isArchived !== undefined ? `?is_archived=${isArchived}` : ''}`).then(r => r.json()),
    createDocumentTemplate: (data: object) => fetchWithAuth('/documents/templates', {
        method: 'POST',
        body: JSON.stringify(data),
    }).then(r => r.json()),
    updateDocumentTemplate: (id: number, data: any) =>
        fetchWithAuth(`/documents/templates/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        }).then(r => r.json()),

    deleteDocumentTemplate: (id: number) =>
        fetchWithAuth(`/documents/templates/${id}`, {
            method: 'DELETE'
        }).then(r => r.json()),

    // Document Categories
    getDocumentCategories: (includeSubcategories = false) =>
        fetchWithAuth(`/documents/categories${includeSubcategories ? '?include_subcategories=true' : ''}`).then(r => r.json()),
    createDocumentCategory: (data: { name: string; description?: string; icon?: string }) =>
        fetchWithAuth('/documents/categories', {
            method: 'POST',
            body: JSON.stringify(data),
        }).then(r => r.json()),

    // Document Subcategories
    getDocumentSubcategories: (categoryId?: number) =>
        fetchWithAuth(`/documents/subcategories${categoryId ? `?category_id=${categoryId}` : ''}`).then(r => r.json()),
    createDocumentSubcategory: (categoryId: number, name: string, icon?: string) =>
        fetchWithAuth(`/documents/subcategories?category_id=${categoryId}&name=${encodeURIComponent(name)}${icon ? `&icon=${icon}` : ''}`, {
            method: 'POST',
        }).then(r => r.json()),
};
