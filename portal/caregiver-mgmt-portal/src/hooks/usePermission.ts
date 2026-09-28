import { useAuth } from '../contexts/AuthContext';

// Role IDs (admin, director, site_director, dsp)
// const ROLE_ADMIN = 1;
// const ROLE_DIRECTOR = 2;
// const ROLE_SITE_DIRECTOR = 3;
// const ROLE_DSP = 4;

type RoleName = 'admin' | 'director' | 'site_director' | 'dsp';
type Permission = 'create' | 'read' | 'update' | 'delete';
type Resource = 'clients' | 'staff' | 'shifts' | 'documents' | 'client_contacts' | 'client_program_enrollments' | 'client_current_residence' | 'client_behavior_configs' | 'behavior_types';

// Permissions matrix based on RBAC_PERMISSIONS.md
// Format: { resource: { role: [permissions] } }
const PERMISSIONS: Record<Resource, Record<RoleName, Permission[]>> = {
    clients: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['read'], // R - read only
        site_director: ['read'], // R (Scoped)
        dsp: ['read'], // R (Scoped)
    },
    client_contacts: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['create', 'read', 'update', 'delete'],
        site_director: ['create', 'read', 'update', 'delete'], // CRUD (Scoped)
        dsp: ['read'], // R (Scoped)
    },
    client_program_enrollments: {
        admin: ['create', 'read', 'delete'],  // CR + End (no update - immutable for HIPAA)
        director: ['create', 'read', 'delete'], // CR + End (same as admin)
        site_director: ['read'], // R (Scoped) - only read per RBAC matrix
        dsp: ['read'], // R (Scoped)
    },
    client_current_residence: {
        admin: ['create', 'read', 'delete'],  // CR + End (no update - immutable for HIPAA)
        director: ['create', 'read', 'delete'], // CR + End (same as admin)
        site_director: ['read'], // R (Scoped)
        dsp: ['read'], // R (Scoped)
    },
    client_behavior_configs: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['create', 'read', 'update', 'delete'],
        site_director: ['read'], // R (Scoped) - read only, admin/director manage configs
        dsp: ['read'], // R (Scoped)
    },
    staff: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['read'], // R - read only
        site_director: ['read'], // R (Scoped)
        dsp: ['read'], // R (Self)
    },
    shifts: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['create', 'read', 'update', 'delete'],
        site_director: ['create', 'read', 'update', 'delete'], // CRUD (Scoped)
        dsp: ['read'], // R (Scoped)
    },
    documents: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['create', 'read', 'update', 'delete'],
        site_director: ['create', 'read', 'update', 'delete'], // CRUD (Scoped) for client_documents
        dsp: ['read'], // R (Scoped)
    },
    behavior_types: {
        admin: ['create', 'read', 'update', 'delete'],
        director: ['create', 'read', 'update', 'delete'],
        site_director: ['read'],
        dsp: ['read'],
    },
};

// Module access for navigation
const MODULE_ACCESS: Record<string, RoleName[]> = {
    dashboard: ['admin', 'director', 'site_director', 'dsp'],
    clients: ['admin', 'director', 'site_director'],
    staff: ['admin', 'director', 'site_director'],
    shifts: ['admin', 'director', 'site_director'],
    documents: ['admin', 'director', 'site_director'],
};

export function usePermission() {
    const { user } = useAuth();

    const hasRole = (roles: RoleName[]): boolean => {
        if (!user) return false;
        return roles.includes(user.role_name as RoleName);
    };

    const hasModuleAccess = (module: string): boolean => {
        if (!user) return false;
        const allowedRoles = MODULE_ACCESS[module];
        if (!allowedRoles) return false;
        return allowedRoles.includes(user.role_name as RoleName);
    };

    // Check specific permission on a resource
    const can = (permission: Permission, resource: Resource): boolean => {
        if (!user) return false;
        const roleName = user.role_name as RoleName;
        const resourcePerms = PERMISSIONS[resource];
        if (!resourcePerms) return false;
        const rolePerms = resourcePerms[roleName];
        if (!rolePerms) return false;
        return rolePerms.includes(permission);
    };

    // Convenience methods
    const canCreate = (resource: Resource) => can('create', resource);
    const canRead = (resource: Resource) => can('read', resource);
    const canUpdate = (resource: Resource) => can('update', resource);
    const canDelete = (resource: Resource) => can('delete', resource);

    const isAdmin = (): boolean => hasRole(['admin']);
    const isDirector = (): boolean => hasRole(['director']);
    const isSiteDirector = (): boolean => hasRole(['site_director']);
    const isAdminOrDirector = (): boolean => hasRole(['admin', 'director']);
    const isManagement = (): boolean => hasRole(['admin', 'director', 'site_director']);

    const canAccessLocation = (locationId: number): boolean => {
        if (!user) return false;
        if (user.role_name === 'admin' || user.role_name === 'director') return true;
        if (user.role_name === 'site_director') {
            return user.assigned_location_id === locationId;
        }
        return false;
    };

    return {
        user,
        hasRole,
        hasModuleAccess,
        can,
        canCreate,
        canRead,
        canUpdate,
        canDelete,
        isAdmin,
        isDirector,
        isSiteDirector,
        isAdminOrDirector,
        isManagement,
        canAccessLocation,
    };
}
