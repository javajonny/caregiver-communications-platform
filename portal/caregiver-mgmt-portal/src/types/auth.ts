// Role types matching backend
export type RoleName = 'admin' | 'director' | 'site_director' | 'dsp';

export interface User {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    work_phone: string | null;
    profile_image_url: string | null;
    role_id: number;
    role_name: RoleName;
    assigned_location_id: number | null;
    session_id: number;
    last_activity: string;
}

export interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
}

export type Permission = 'create' | 'read' | 'update' | 'delete';

export type ResourceTable =
    | 'clients'
    | 'staff'
    | 'shifts'
    | 'shift_templates'
    | 'tasks'
    | 'shift_daily_logs'
    | 'document_templates'
    | 'client_documents';
